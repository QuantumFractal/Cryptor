#Client Class that handles files transfers, authentication, and encryption
from dropbox import client, session
import gnupg, os

class CryptorClient:
	
	def __init__(self, settings):
		""" Constructor for CryptorClient

		Args:
			settings - Settings object generated from a load_config

		"""

		self.settings = settings

		self.gpg = gnupg.GPG(gnupghome=self.settings['gpg_home'])
		self.normal_dir = self.settings['normal_folder_path']
		self.hidden_dir = self.settings['hidden_folder_path']
		self.db_home = self.settings['db_home']+'/'

		sess = session.DropboxSession(self.settings['app_key'], self.settings['app_secret'], 'dropbox')
		sess.set_token(self.settings['client_key'], self.settings['client_secret'])
		self.db = client.DropboxClient(sess)

		self.local_delta = dict ([(f, None) for f in os.listdir (self.normal_dir)])
		self.remote_delta = self.db.delta(path_prefix=self.db_home[:-1])

	def push(self, filename):
		"""
		Description: Pushes file by encrypting (encrypt) and then uploading (upload) it to dropbox.

		Args:
			filename - string of the file to be pushed

		Returns: True if file was successfully uploaded, false if otherwise
		"""
		if not isinstance(filename, str):
			return False

		try:
			file_object = open(self.normal_dir+filename, 'rb')
		except IOError:
			return False

		self.encrypt(file_object)

		try:
			encrypted_file_object = open(self.hidden_dir+filename+'.crypto' ,'rb')
		except IOError:
			return False

		self.upload(encrypted_file_object)

		file_object.close()
		encrypted_file_object.close()

		return True;


	def pull(self, filename):
		"""
		Description: Pulls file by downloading file (if it exists) then decrypting it.

		Args:
			filename - string of the file to be pulled

		Returns: True if file was successfully pulled, false if otherwise
		"""

		if not isinstance(filename, str):
			return False

		self.download(filename+'.crypto')
		encrypted_file_object = open(self.hidden_dir+filename+'.crypto', 'rb')
		self.decrypt(encrypted_file_object)

		return True

	def encrypt(self, file_object):
		"""
		Description: Encrypts a file using GPG keys

		Args:
			file_object - file object to be encrypted

		Returns: True if file was successfully encrypted false if otherwise
		"""
		if not isinstance(file_object, file):
			return False
		name = file_object.name.split('\\')[-1]
		file_path = self.hidden_dir+name+'.crypto'
		self.gpg.encrypt_file(file_object, 'Cryptor', always_trust=True, output=file_path)

		return True


	def decrypt(self, file_object):
		"""
		Description: Decrypts a file using GPG keys

		Args:
			file_object - file object to be decrypted

		Returns: True if file was successfully decrypted false if otherwise
		"""
		if not isinstance(file_object, file):
			return False

		name = file_object.name.split('\\')[-1]
		passphrase = self.settings['gpg_key']
		self.gpg.decrypt_file(file_object, passphrase=passphrase, always_trust=True, output=self.normal_dir+name[:-7])

		return True


	def upload(self, file_object):
		name = file_object.name.split('\\')[-1]
		self.db.put_file(self.db_home+name, file_object, overwrite=True)


	def download(self, filename):
		encrypted_file = open(self.hidden_dir+filename, 'wb')
		with self.db.get_file(self.db_home+filename) as f:
			encrypted_file.write(f.read())
		encrypted_file.close()

	def sync(self):
		local = os.listdir(self.normal_dir)
		remote = []
		for file in self.db.metadata(self.db_home)['contents']:
			remote.append(file['path'].split('/')[0][:-7])

		if set(local) == set(remote):
			return True;

		local_added, local_removed = self.get_local_delta()
		remote_added, remote_removed = self.get_remote_delta()

		print local_added, local_removed
		print remote_added, remote_removed

		for file in local_removed:
			self.delete_remote(file)

		for file in remote_removed:
			self.delete_local(file)

		for file in local_added:
			self.push(file)

		for file in remote_added:
			self.pull(file)




	def delete_local(self, filename):
		try:
			os.remove(self.normal_dir+filename)
		except Exception:
			return False

		try:
			os.remove(self.hidden_dir+filename+'.crypto')
		except Exception:
			return False
		return True

	def delete_remote(self, filename):
		try:
			self.db.file_delete(self.db_home+filename+'.crypto')
		except Exception:
			return False
		return True



	def delete(self, filename):
		self.delete_remote(filename)
		self.delete_local(filename)


	def verify_environment(self):
		if not os.path.isdir(self.normal_dir):
			return False
		if not os.path.isdir(self.hidden_dir):
			return False
		if not os.path.isdir(self.settings['gpg_home']):
			return False
		return True


	def get_local_delta(self):
		delta = dict ([(f, None) for f in os.listdir (self.normal_dir)])
		added = [f for f in delta if not f in self.local_delta]
		removed = [f for f in self.local_delta if not f in delta]
		# if added:
		# 	for f in added:
		# 		pass
		# 		#client.push(f)
		# 	print "Added: ", ", ".join (added)
		#
		# if removed:
		# 	for f in removed:
		# 		pass
		# 		#client.delete(f)
		# 	print "Removed: ", ", ".join (removed)

		self.local_delta = delta

		return added, removed


	def get_remote_delta(self):
		delta = self.db.delta(self.remote_delta['cursor'], self.settings['db_home'])
		diff = delta['entries']

		changed = []
		removed = []

		if diff:
			for change in diff:
				if not '.crypto' in change[0]:
					continue
				#Determine if it's an addition, [subtraction, amendment
				change[0] = change[0].split('/')[-1]
				change[0] = change[0][:-7]
				#If there's a change
				if change[1]:

					changed.append(change[0])

				else:
					removed.append(change[0])


		else:
			pass

		self.remote_delta = delta

		return changed, removed