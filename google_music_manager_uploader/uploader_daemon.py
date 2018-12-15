#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import time
import logging
import os
import glob
import netifaces
import argparse

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from gmusicapi import Musicmanager
from gmusicapi.exceptions import CallFailure

__DEFAULT_IFACE__ = netifaces.gateways()['default'][netifaces.AF_INET][1]
__DEFAULT_MAC__ = netifaces.ifaddresses(__DEFAULT_IFACE__)[netifaces.AF_LINK][0]['addr'].upper()


class MusicToUpload(FileSystemEventHandler):
    def on_created(self, event) -> None:
        self.logger.info("Detected new files!")
        if os.path.isdir(self.path):
            files = [file for file in glob.glob(glob.escape(self.path) + '/**/*', recursive=True)]
            for file_path in files:
                upload_file(self.api, file_path, self.logger, remove=self.remove)
        else:
            upload_file(self.api, event.src_path, self.logger, remove=self.remove)


def upload_file(api: Musicmanager, file_path: str, logger: logging.Logger, remove: bool = False) -> None:
    """
    Uploads a specific file by its path
    :param api: Musicmanager object to upload file though
    :param file_path: Path to MP3 file to upload
    :param logger: logging.Logger object for logs
    :param remove: Boolean. should remove file? False by default
    :raises CallFailure:
    :return:
    """
    retry = 5
    while retry > 0:
        try:
            if os.path.isfile(file_path):
                logger.info("Uploading : " + file_path)
                uploaded, matched, not_uploaded = api.upload(file_path, True)
                if remove and (uploaded or matched):
                    os.remove(file_path)
            retry = 0
        except CallFailure as e:
            error_message = str(e)
            if "401" in error_message:
                retry -= 1
            elif "502" in error_message:
                retry -= 1
                time.sleep(30)
            else:
                raise e


def upload(
    directory: str = '.',
    oauth: str = os.environ['HOME'] + '/oauth',
    remove: bool = False,
    uploader_id: str = __DEFAULT_MAC__,
    oneshot: bool = False
) -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Init Daemon - Press Ctrl+C to quit")

    api = Musicmanager()
    if not api.login(oauth, uploader_id):
        print("Error with oauth credentials")
        sys.exit(1)
    observer = None
    if not oneshot:
        event_handler = MusicToUpload()
        event_handler.api = api
        event_handler.oauth = oauth
        event_handler.uploader_id = uploader_id
        event_handler.path = directory
        event_handler.remove = remove
        event_handler.logger = logger
        observer = Observer()
        observer.schedule(event_handler, directory, recursive=True)
        observer.start()
    files = [file for file in glob.glob(glob.escape(directory) + '/**/*', recursive=True)]
    for file_path in files:
        upload_file(api, file_path, logger, remove=remove)
    if oneshot:
        sys.exit(0)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", '-d', default='.', help="Music Folder to upload from (default: .)")
    parser.add_argument(
        "--oauth",
        '-a',
        default=os.environ['HOME'] + '/oauth',
        help="Path to oauth file (default: ~/oauth)"
    )
    parser.add_argument("-r", "--remove", action='store_true', help="Remove files if present (default: False)")
    parser.add_argument(
        "--uploader_id",
        '-u',
        default=__DEFAULT_MAC__,
        help="Uploader identification (should be an uppercase MAC address) (default: <current eth0 MAC address>)"
    )
    parser.add_argument("--oneshot", '-o', action='store_true', help="Upload folder and exit (default: False)")
    args = parser.parse_args()
    upload(
        directory=args.directory,
        oauth=args.oauth,
        remove=args.remove,
        uploader_id=args.uploader_id,
        oneshot=args.oneshot
    )


if __name__ == "__main__":
    main()
