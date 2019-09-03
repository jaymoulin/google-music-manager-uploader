#!/usr/bin/env python
# coding: utf-8

import sys
import time
import logging
import os
import glob
import netifaces
import argparse
import requests

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .manager import Manager as Musicmanager
from gmusicapi.exceptions import CallFailure

__DEFAULT_IFACE__ = netifaces.gateways()['default'][netifaces.AF_INET][1]
__DEFAULT_MAC__ = netifaces.ifaddresses(__DEFAULT_IFACE__)[netifaces.AF_LINK][0]['addr'].upper()


class DeduplicateApi:
    def __init__(self, uri: str) -> None:
        self.uri = uri

    def exists(self, file_path: str) -> bool:
        result = requests.request('GET', self.uri + "/", data={"path": file_path})
        return result.status_code == 200 or result.status_code == 204

    def save(self, file_path: str) -> None:
        requests.request('POST', self.uri + "/", data={"path": file_path})

    def remove(self, file_path: str) -> None:
        requests.request('DELETE', self.uri + "/", data={"path": file_path})


class MusicToUpload(FileSystemEventHandler):
    def on_created(self, event) -> None:
        self.logger.info("Detected new files!")
        if os.path.isdir(self.path):
            files = [file for file in glob.glob(glob.escape(self.path) + '/**/*', recursive=True)]
            for file_path in files:
                upload_file(
                    api=self.api,
                    file_path=file_path,
                    logger=self.logger,
                    remove=self.remove,
                    deduplicate_api=self.deduplicate_api,
                )
        else:
            upload_file(
                api=self.api,
                file_path=event.src_path,
                logger=self.logger,
                remove=self.remove,
                deduplicate_api=self.deduplicate_api,
            )


def upload_file(
    api: Musicmanager,
    file_path: str,
    logger: logging.Logger,
    remove: bool = False,
    deduplicate_api: DeduplicateApi = None,
) -> None:
    """
    Uploads a specific file by its path
    :param api: Musicmanager. object to upload file though
    :param file_path: Path to MP3 file to upload
    :param logger: logging.Logger object for logs
    :param remove: Boolean. should remove file? False by default
    :param deduplicate_api: DeduplicateApi. Api for deduplicating uploads. None by default
    :raises CallFailure:
    :return:
    """
    retry = 5
    while retry > 0:
        try:
            if os.path.isfile(file_path):
                logger.info("Uploading %s? " % file_path)
                if deduplicate_api:
                    exists = deduplicate_api.exists(file_path)
                    logger.info("Deduplicate API: file exists? " + "yes" if exists else "no")
                    if exists:
                        return
                uploaded, matched, not_uploaded = api.upload(file_path, True)
                if not_uploaded:
                    logger.info("Not uploaded %s" % file_path)
                if (uploaded or matched) and deduplicate_api:
                    deduplicate_api.save(file_path)
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
    oneshot: bool = False,
    deduplicate_api: str = None,
) -> None:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("Init Daemon - Press Ctrl+C to quit")

    api = Musicmanager()
    if not api.login(oauth, uploader_id):
        raise ValueError("Error with oauth credentials")
    observer = None
    deduplicate = DeduplicateApi(deduplicate_api) if deduplicate_api else None
    if not oneshot:
        event_handler = MusicToUpload()
        event_handler.api = api
        event_handler.oauth = oauth
        event_handler.uploader_id = uploader_id
        event_handler.path = directory
        event_handler.remove = remove
        event_handler.logger = logger
        event_handler.deduplicate_api = deduplicate
        observer = Observer()
        observer.schedule(event_handler, directory, recursive=True)
        observer.start()
    files = [file for file in glob.glob(glob.escape(directory) + '/**/*', recursive=True)]
    for file_path in files:
        upload_file(api, file_path, logger, remove=remove, deduplicate_api=deduplicate)
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
    parser.add_argument(
        "--directory",
        '-d',
        default='.',
        help="Music Folder to upload from (default: .)"
    )
    parser.add_argument(
        "--oauth",
        '-a',
        default=os.environ['HOME'] + '/oauth',
        help="Path to oauth file (default: ~/oauth)"
    )
    parser.add_argument(
        "-r",
        "--remove",
        action='store_true',
        help="Remove files if present (default: False)"
    )
    parser.add_argument(
        "--uploader_id",
        '-u',
        default=__DEFAULT_MAC__,
        help="Uploader identification (should be an uppercase MAC address) (default: <current eth0 MAC address>)"
    )
    parser.add_argument(
        "--oneshot",
        '-o',
        action='store_true',
        help="Upload folder and exit (default: False)"
    )
    parser.add_argument(
        "--deduplicate_api",
        '-w',
        default=None,
        help="Deduplicate API (should be HTTP and compatible with the manifest (see README)) (default: None)"
    )
    args = parser.parse_args()
    upload(
        directory=args.directory,
        oauth=args.oauth,
        remove=args.remove,
        uploader_id=args.uploader_id,
        oneshot=args.oneshot,
        deduplicate_api=args.deduplicate_api,
    )


if __name__ == "__main__":
    main()
