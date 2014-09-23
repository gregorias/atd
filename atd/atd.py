#!/usr/bin/env python

import getpass
import os.path
from paramiko import AutoAddPolicy, SSHClient
import paramiko
import posixpath
import stat
import sys
from tpb import TPB


THEPIRATEBAY = 'https://thepiratebay.org'
SSH_PORT = 22

def torrent_size_specifier_to_multiplier(size_specifier):
    if size_specifier == 'KiB':
        return 10**3
    elif size_specifier == 'MiB':
        return 10**6
    elif size_specifier == 'GiB':
        return 10**9
    else:
        return 10**0

def torrent_size_to_bytes(torrent_size):
    size, specifier = torrent_size.split()
    return int(float(size) * torrent_size_specifier_to_multiplier(specifier))

class TorrentFinder:
    '''A class which handles finding good torrents under given keyword.'''
    def __init__(self):
        self.tpb = TPB(THEPIRATEBAY)

    def find(self, keyword, filters=[], min_seeders=0, category=0):
        '''Finds torrents under given keyword which also pass specified
        filters.

        Returns:
            A list of found tpb.Torrent objects.
        '''
        search = self.tpb.search(keyword, category=category).multipage()
        good_torrents = []
        for torrent in search:
            if (torrent.seeders < min_seeders):
                break

            if all([filter_function(torrent) for filter_function in filters]):
                good_torrents.append(torrent)
        return good_torrents

def select_torrent(torrents, expected_min_size=0):
    '''Select one torrent which looks like the best candidate from a list of
    torrents.'''
    for torrent in torrents:
        if torrent_size_to_bytes(torrent.size) >= expected_min_size:
            return torrent

    if len(torrents) > 0:
        return torrents[0]

    return None

class SSHDownloader:
    '''SSHDownloader handles downloading a torrent on remote SSH server and then
    copying it to local directory.'''

    def __init__(self, remote_host, username, password):
        self.remote_host = remote_host
        self.username = username
        self.password = password

    def download(self, torrent, remote_output_dir, local_output_dir):
        '''Downloads given file to remote_output_dir on remote host then
        downloads it locally'''
        self.__download_on_remote_host(torrent, remote_output_dir)
        self.__move_downloaded_files_from_remote_to_local(remote_output_dir,
                local_output_dir)

    def __download_on_remote_host(self, torrent, remote_output_dir):
        client = SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(AutoAddPolicy()) 
        client.connect(self.remote_host, username=self.username,
                password=self.password)

        try:
            print("Downloading: %s with magnet_link: %s." % (torrent.title,
                torrent.magnet_link))
            stdin, stdout, stderr = client.exec_command(
                    './bin/bin/aria2c --seed-time=0 --dir=%s %s' % 
                    (remote_output_dir, torrent.magnet_link))

            for line in stdout:
                print line
        finally:
            client.close()

    def __move_downloaded_files_from_remote_to_local(self,
            remote_output_dir,
            local_output_dir):
        transport = paramiko.Transport((STUDENTS_HOST, SSH_PORT))
        transport.connect(username=USERNAME, password=PASSWORD)
        try:
            sftp = paramiko.SFTPClient.from_transport(transport)
            self.__sftp_walk(sftp, remote_output_dir, local_output_dir)
            sftp.remove(remote_output_dir)
        finally:
            transport.close()

    def __move_file_from_remote_to_local(self, sftp, remote_path, local_path):
        sftp.get(remote_path, local_path)

    def __sftp_walk(self, sftp, remote_output_dir, local_output_dir):
        dir_list = sftp.listdir_attr(remote_output_dir)
        for file_attr in dir_list:
            local_output_filename = os.path.join(
                    local_output_dir,
                    file_attr.filename)
            remote_output_filename = posixpath.join(
                    remote_output_dir,
                    file_attr.filename)
            if stat.S_ISDIR(file_attr.st_mode):
                os.mkdir(local_output_filename)

                self.sftp_walk(
                        sftp,
                        remote_output_filename,
                        local_output_filename)
            else:
                self.__move_file_from_remote_to_local(sftp,
                        remote_output_filename,
                        local_output_filename)
            sftp.remove(remote_output_filename)

class MaxSizeFilter:
    '''Filter which discards torrent larger than given size.'''
    def __init__(self, max_size):
        self.max_size = max_size

    def __call__(self, torrent):
        return torrent_size_to_bytes(torrent.size) < self.max_size

if __name__ == '__main__':
    sys.stdout.write('Provide host: ')
    host = sys.stdin.readline().strip()
    sys.stdout.write('Provide username: ')
    username = sys.stdin.readline().strip()
    password  = getpass.getpass('Provide password: ')
    sys.stdout.write('Provide keyword: ')
    keyword = sys.stdin.readline().strip()
    finder = TorrentFinder()
    size_filter = MaxSizeFilter(10**9)
    good_torrents = finder.find(keyword, filters=[size_filter], min_seeders=5)
    chosen_torrent = select_torrent(good_torrents, expected_min_size=200 * 10**6)

    if chosen_torrent == None:
        sys.exit("Could not find any good torrent.")

    print('Torrent: ' + chosen_torrent.title) 
    print('... size: ' + chosen_torrent.size)
    print('... seeders: ' + str(chosen_torrent.seeders))
    print('... files: ' + str(chosen_torrent.files))
    print('')
    downloader = SSHDownloader(host, username, password)
    downloader.download(chosen_torrent, 'public_html', '/home/grzesiek/Downloads')
