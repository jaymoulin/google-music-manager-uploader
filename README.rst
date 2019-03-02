.. image:: https://raw.githubusercontent.com/jaymoulin/google-music-manager-uploader/master/logo.png
    :alt: logo
    :target: http://github.com/jaymoulin/google-music-manager-uploader


===============================
Google Music Manager - Uploader
===============================



.. image:: https://img.shields.io/github/release/jaymoulin/google-music-manager.svg
    :alt: latest release
    :target: http://github.com/jaymoulin/google-music-manager/releases
.. image:: https://img.shields.io/pypi/v/google-music-manager-uploader.svg
    :alt: PyPI version
    :target: https://pypi.org/project/google-music-manager-uploader/
.. image:: https://github.com/jaymoulin/jaymoulin.github.io/raw/master/btc.png
    :alt: Bitcoin donation
    :target: https://m.freewallet.org/id/374ad82e/btc
.. image:: https://github.com/jaymoulin/jaymoulin.github.io/raw/master/ltc.png
    :alt: Litecoin donation
    :target: https://m.freewallet.org/id/374ad82e/ltc
.. image:: https://github.com/jaymoulin/jaymoulin.github.io/raw/master/ppl.png
    :alt: PayPal donation
    :target: https://www.paypal.me/jaymoulin
.. image:: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png
    :alt: Buy me a coffee
    :target: https://www.buymeacoffee.com/3Yu8ajd7W

This program will replace former Google MusicManager to upload your music library to Google Music

This work is based upon `Simon Weber's Google Music API <https://github.com/simon-weber/gmusicapi>`_.

Installation
------------

Avconv is needed to convert some of your files due to Google's MP3 constraint
also, this program needs `watchdog`, `gmusicapi`, `netifaces`, `requests` and `bs4` Python libraries to work.

.. code::

    apt-get install python3-pip libav-tools build-essential
    pip3 install google-music-manager-uploader


Once installed, You have to authenticate to Google Music via the `google-music-auth` command

.. code::

    # Usage google-music-auth [path_to_oauth_cred_file=~/oauth]


If first parameter is not defined, the script will try to store/load your oauth credentials through the `~/oauth` file.

Then follow prompted instructions.

You will be asked to go to a Google URL to allow the connection:

.. code::

    Visit the following url:
        https://accounts.google.com/o/oauth2/v2/auth?client_id=XXXXXXXXXXX.apps.googleusercontent.com&access_type=offline&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fmusicmanager&response_type=code&redirect_uri=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob
    Follow the prompts, then paste the auth code here and hit enter:

Usage
-----

Uploader
~~~~~~~~

This program will scan a given directory for new elements to upload them to Google Music.
First, launch the daemon to watch a directory new inputs.

It will *NOT* upload already existing files, *ONLY* new files while the daemon is running. (Please contribute if you want this to change)

.. code::

    usage: google-music-uploader [-h] [--directory DIRECTORY] [--oauth OAUTH] [-r]
                              [--uploader_id UPLOADER_ID] [-o] [--deduplicate_api DEDUPLICATE_API]

    optional arguments:
      -h, --help            show this help message and exit
      --directory DIRECTORY, -d DIRECTORY
                            Music Folder to upload from (default: .)
      --oauth OAUTH, -a OAUTH
                            Path to oauth file (default: ~/oauth)
      -r, --remove          Remove files if present (default: False)
      --uploader_id UPLOADER_ID, -u UPLOADER_ID
                            Uploader identification (should be an uppercase MAC
                            address) (default: <current eth0 MAC address>)
      -o, --oneshot         Upload folder and exit (default: False)
      -w DEDUPLICATE_API, --deduplicate_api DEDUPLICATE_API
                            Deduplicate API (should be HTTP and compatible with
                            the manifest (see README)) (default: None)

Deduplicate
~~~~~~~~~~~

This program will send all files or the specified file to the deduplication API

.. code::

    usage: google-music-upload-deduplicate [-h] --deduplicate_api DEDUPLICATE_API
                                       [--directory DIRECTORY] [--file FILE]
                                       [--remove]

    optional arguments:
      -h, --help            show this help message and exit
      --directory DIRECTORY, -d DIRECTORY
                            Music Folder to deduplicate
      --file FILE, -f FILE
                            Music file path to deduplicate
      -r, --remove          Unmark specified file/folder (default: False)
      -w DEDUPLICATE_API, --deduplicate_api DEDUPLICATE_API
                            Deduplicate API (should be HTTP and compatible with
                            the manifest (see README)) (default: None)

=================
Deduplication API
=================

Preface
-------

This API is completely optional. You don't have to implement this. It will only help you to avoid useless Google calls

You can use your own API implementation to avoid sampling + Google upload.
This API should match with the following requirements.

You may want to use this existing one : `Google MusicManager Deduplicate API <https://github.com/jaymoulin/google-musicmanager-dedup-api>`_.

Exists
------

+------+--------+--------------------------+----------------------------------------------------+
| path | method | parameter                | status code                                        |
+======+========+==========================+====================================================+
| /    | GET    | name | description       | value             | description                    |
|      |        +------+-------------------+-------------------+--------------------------------+
|      |        | path | path of your file | 200 or 204        | Your file was already uploaded |
|      |        |      |                   +-------------------+--------------------------------+
|      |        |      |                   | 404 (or whatever) | Your file was NOT uploaded     |
+------+--------+------+-------------------+-------------------+--------------------------------+

Saving
------

+------+--------+--------------------------+-------------------------------------------------+
| path | method | parameter                | status code                                     |
+======+========+==========================+=================================================+
| /    | POST   | name | description       | value    | description                          |
|      |        +------+-------------------+----------+--------------------------------------+
|      |        | path | path of your file | whatever | Status code does not change anything |
+------+--------+------+-------------------+----------+--------------------------------------+

Removing
--------

+------+--------+--------------------------+-------------------------------------------------+
| path | method | parameter                | status code                                     |
+======+========+==========================+=================================================+
| /    | DELETE | name | description       | value    | description                          |
|      |        +------+-------------------+----------+--------------------------------------+
|      |        | path | path of your file | whatever | Status code does not change anything |
+------+--------+------+-------------------+----------+--------------------------------------+

=====
About
=====

Requirements
------------

Google Music Uploader works with Python 3 or above.
It requires `Simon Weber's Google Music API <https://github.com/simon-weber/gmusicapi>`_ and `Watchdog <https://pypi.python.org/pypi/watchdog>`_.

Submitting bugs and feature requests
------------------------------------

Bugs and feature request are tracked on GitHub

Author
------

Jay MOULIN jaymoulin@gmail.com See also the list of contributors which participated in this program.

License
-------

Google Music Uploader is licensed under the MIT License
