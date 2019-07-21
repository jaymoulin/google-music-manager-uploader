#!/usr/bin/env python
# coding: utf-8

from gmusicapi import Musicmanager
from past.builtins import basestring
from gmusicapi.utils import utils
from gmusicapi.exceptions import NotLoggedIn
from gmusicapi.protocol import musicmanager, upload_pb2, locker_pb2
import mutagen
import base64
import time


class Manager(Musicmanager):
    @utils.accept_singleton(basestring)
    @utils.empty_arg_shortcircuit(return_code='{}')
    def upload(
        self,
        filepaths,
        enable_matching=False,
        enable_transcoding=True,
        transcode_quality='320k',
        include_album_art=True,
    ):
        """Uploads the given filepaths.
        All non-mp3 files will be transcoded before being uploaded.
        This is a limitation of Google's backend.
        An available installation of ffmpeg or avconv is required in most cases:
        see `the installation page
        <https://unofficial-google-music-api.readthedocs.io/en
        /latest/usage.html?#installation>`__ for details.
        Returns a 3-tuple ``(uploaded, matched, not_uploaded)`` of dictionaries, eg::
            (
                {'<filepath>': '<new server id>'},               # uploaded
                {'<filepath>': '<new server id>'},               # matched
                {'<filepath>': '<reason, eg ALREADY_EXISTS>'}    # not uploaded
            )
        :param filepaths: a list of filepaths, or a single filepath.
        :param enable_matching: if ``True``, attempt to use `scan and match
          <http://support.google.com/googleplay/bin/answer.py?hl=en&answer=2920799&topic=2450455>`__
          to avoid uploading every song.
          This requires ffmpeg or avconv.
          **WARNING**: currently, mismatched songs can *not* be fixed with the 'Fix Incorrect Match'
          button nor :py:func:`report_incorrect_match
          <gmusicapi.clients.Webclient.report_incorrect_match>`.
          They would have to be deleted and reuploaded with matching disabled
          (or with the Music Manager).
          Fixing matches from gmusicapi may be supported in a future release; see issue `#89
          <https://github.com/simon-weber/gmusicapi/issues/89>`__.
        :param enable_transcoding:
          if ``False``, non-MP3 files that aren't matched using `scan and match
          <http://support.google.com/googleplay/bin/answer.py?hl=en&answer=2920799&topic=2450455>`__
          will not be uploaded.
        :param transcode_quality: if int, pass to ffmpeg/avconv ``-q:a`` for libmp3lame
          (`lower-better int,
          <http://trac.ffmpeg.org/wiki/Encoding%20VBR%20(Variable%20Bit%20Rate)%20mp3%20audio>`__).
          If string, pass to ffmpeg/avconv ``-b:a`` (eg ``'128k'`` for an average bitrate of 128k).
          The default is 320kbps cbr (the highest possible quality).
        :param include_album_art: If ``False``, do not upload embedded album art.
          If string, upload external album art at given filepath.
          Google Music supports GIF, JPEG, and PNG image formats.
        All Google-supported filetypes are supported; see `Google's documentation
        <http://support.google.com/googleplay/bin/answer.py?hl=en&answer=1100462>`__.
        If ``PERMANENT_ERROR`` is given as a not_uploaded reason, attempts to reupload will never
        succeed. The file will need to be changed before the server will reconsider it; the easiest
        way is to change metadata tags (it's not important that the tag be uploaded, just that the
        contents of the file change somehow).
        """

        if self.uploader_id is None or self.uploader_name is None:
            raise NotLoggedIn("Not authenticated as an upload device;"
                              " run Api.login(...perform_upload_auth=True...)"
                              " first.")

        # TODO there is way too much code in this function.

        # To return.
        uploaded = {}
        matched = {}
        not_uploaded = {}

        # Gather local information on the files.
        local_info = {}  # {clientid: (path, Track)}
        for path in filepaths:
            try:
                track = musicmanager.UploadMetadata.fill_track_info(path)
            except BaseException as e:
                self.logger.exception("problem gathering local info of '%r'", path)

                user_err_msg = str(e)

                if 'Non-ASCII strings must be converted to unicode' in str(e):
                    # This is a protobuf-specific error; they require either ascii or unicode.
                    # To keep behavior consistent, make no effort to guess - require users
                    # to decode first.
                    user_err_msg = ("nonascii bytestrings must be decoded to unicode"
                                    " (error: '%s')" % user_err_msg)

                not_uploaded[path] = user_err_msg
            else:
                local_info[track.client_id] = (path, track)

        if not local_info:
            return uploaded, matched, not_uploaded

        # TODO allow metadata faking

        # Upload metadata; the server tells us what to do next.
        res = self._make_call(
            musicmanager.UploadMetadata,
            [t for (path, t) in local_info.values()],
            self.uploader_id
        )

        # TODO checking for proper contents should be handled in verification
        md_res = res.metadata_response

        responses = [r for r in md_res.track_sample_response]
        sample_requests = [req for req in md_res.signed_challenge_info]

        # Send scan and match samples if requested.
        for sample_request in sample_requests:
            path, track = local_info[sample_request.challenge_info.client_track_id]

            bogus_sample = None
            if not enable_matching:
                bogus_sample = b''  # just send empty bytes

            album_art_image = None
            if include_album_art:
                if include_album_art is True:  # Load embedded album art.
                    song = mutagen.File(path)

                    if isinstance(song, mutagen.mp3.MP3):
                        # Search through all the APIC frames to find the cover (type 3).
                        for pic in song.tags.getall('APIC'):
                            if pic.type == 3:
                                album_art_image = pic.data
                    elif isinstance(song, mutagen.flac.FLAC):
                        # Search through all the picture frames to find the cover (type 3).
                        for pic in song.pictures:
                            if pic.type == 3:
                                album_art_image = pic.data
                                break
                    elif isinstance(song, mutagen.mp4.MP4):
                        if 'covr' in song:
                            album_art_image = song['covr'][0]
                    elif isinstance(song, mutagen.asf.ASF):
                        if 'WM/Picture' in song:
                            # Search through all the WM/Picture frames to find the cover (type 3).
                            for pic in song['WM/Picture']:
                                data = bytes(pic)
                                if data[0] == 3:
                                    # Parse out the image data according to the WM_PICTURE spec:
                                    # 1 byte type + 4 bytes data length + null-terminated mime +
                                    # null-terminated description + data
                                    pos = 5
                                    while data[pos:pos + 2] != b"\x00\x00":
                                        pos += 2
                                    pos += 2
                                    while data[pos:pos + 2] != b"\x00\x00":
                                        pos += 2

                                    album_art_image = data[pos + 2:]
                                    break
                    elif isinstance(song, mutagen.oggvorbis.OggVorbis):
                        if 'metadata_block_picture' in song:
                            # Search through all the picture frames to find the cover (type 3).
                            for pic in song['metadata_block_picture']:
                                # Mutagen does not parse out the picture fields to attributes
                                # like with FLAC, so we use the FLAC Picture class to do so.
                                # Picture blocks are base64 encoded in Ogg Vorbis.
                                picture = mutagen.flac.Picture(base64.b64decode(pic))

                                if picture.type == 3:
                                    album_art_image = picture.data
                                    break
                else:  # Load external album art.
                    try:
                        with open(include_album_art, 'rb') as f:
                            album_art_image = f.read()
                    except OSError:
                        self.logger.warning(
                            "Image file: %r cannot be read. Uploading %r without album art.",
                            include_album_art, path
                        )

            try:
                res = self._make_call(
                    musicmanager.ProvideSample,
                    path,
                    sample_request,
                    track,
                    self.uploader_id,
                    bogus_sample,
                    album_art_image,
                )

            except (IOError, ValueError) as e:
                self.logger.warning("couldn't create scan and match sample for '%r': %s", path, str(e))
                not_uploaded[path] = str(e)
            else:
                responses.extend(res.sample_response.track_sample_response)

        # Read sample responses and prep upload requests.
        to_upload = {}  # {serverid: (path, Track, do_not_rematch?)}
        for sample_res in responses:
            path, track = local_info[sample_res.client_track_id]

            if sample_res.response_code == upload_pb2.TrackSampleResponse.MATCHED:
                self.logger.info("matched '%r' to sid %s", path, sample_res.server_track_id)

                matched[path] = sample_res.server_track_id

                if not enable_matching:
                    self.logger.error("'%r' was matched without matching enabled", path)

            elif sample_res.response_code == upload_pb2.TrackSampleResponse.UPLOAD_REQUESTED:
                to_upload[sample_res.server_track_id] = (path, track, False)

            else:
                # there was a problem
                # report the symbolic name of the response code enum for debugging
                enum_desc = upload_pb2._TRACKSAMPLERESPONSE.enum_types[0]
                res_name = enum_desc.values_by_number[sample_res.response_code].name

                err_msg = "TrackSampleResponse code %s: %s" % (sample_res.response_code, res_name)

                if res_name == 'ALREADY_EXISTS':
                    # include the sid, too
                    # this shouldn't be relied on externally, but I use it in
                    # tests - being surrounded by parens is how it's matched
                    err_msg += "(%s)" % sample_res.server_track_id

                self.logger.warning("upload of '%r' rejected: %s", path, err_msg)
                not_uploaded[path] = err_msg

        # Send upload requests.
        if to_upload:
            # TODO reordering requests could avoid wasting time waiting for reup sync
            self._make_call(musicmanager.UpdateUploadState, 'start', self.uploader_id)

            for server_id, (path, track, do_not_rematch) in to_upload.items():
                # It can take a few tries to get an session.
                should_retry = True
                attempts = 0

                while should_retry and attempts < 10:
                    session = self._make_call(
                        musicmanager.GetUploadSession,
                        self.uploader_id,
                        len(uploaded),
                        track,
                        path,
                        server_id,
                        do_not_rematch,
                    )
                    attempts += 1

                    got_session, error_details = \
                        musicmanager.GetUploadSession.process_session(session)

                    if got_session:
                        self.logger.info("got an upload session for '%r'", path)
                        break

                    should_retry, reason, error_code = error_details
                    self.logger.debug(
                        "problem getting upload session: %s\ncode=%s retrying=%s",
                        reason,
                        error_code,
                        should_retry
                    )

                    if error_code == 200 and do_not_rematch:
                        # reupload requests need to wait on a server sync
                        # 200 == already uploaded, so force a retry in this case
                        should_retry = True

                    time.sleep(6)  # wait before retrying
                else:
                    err_msg = "GetUploadSession error %s: %s" % (error_code, reason)

                    self.logger.warning("giving up on upload session for '%r': %s", path, err_msg)
                    not_uploaded[path] = err_msg

                    continue  # to next upload

                # got a session, do the upload
                # this terribly inconsistent naming isn't my fault: Google--
                session = session['sessionStatus']
                external = session['externalFieldTransfers'][0]

                session_url = external['putInfo']['url']
                content_type = external.get('content_type', 'audio/mpeg')

                if track.original_content_type != locker_pb2.Track.MP3:
                    if enable_transcoding:
                        try:
                            self.logger.info("transcoding '%r' to mp3", path)
                            contents = utils.transcode_to_mp3(path, quality=transcode_quality)
                        except (IOError, ValueError) as e:
                            self.logger.warning("error transcoding %r: %s", path, e)
                            not_uploaded[path] = "transcoding error: %s" % e
                            continue
                    else:
                        not_uploaded[path] = "transcoding disabled"
                        continue
                else:
                    with open(path, 'rb') as f:
                        contents = f.read()

                upload_response = self._make_call(musicmanager.UploadFile, session_url, content_type, contents)

                success = upload_response.get('sessionStatus', {}).get('state')
                if success:
                    uploaded[path] = server_id
                else:
                    # 404 == already uploaded? serverside check on clientid?
                    self.logger.debug("could not finalize upload of '%r'. response: %s",
                                      path, upload_response)
                    not_uploaded[path] = 'could not finalize upload; details in log'

            self._make_call(musicmanager.UpdateUploadState, 'stopped', self.uploader_id)

        return uploaded, matched, not_uploaded
