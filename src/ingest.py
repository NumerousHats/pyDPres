"""Perform ingest functions and create object record for file(s)"""

import hashlib
import logging
from datetime import datetime
import uuid
import subprocess
from session import *
import os

import sqlalchemy.exc

import format_specific
import db_classes


class DetermineFormat:
    def __init__(self, filename):
        fido_command = ["fido", "-matchprintf",
                        "OK\n%(info.puid)s\n%(info.formatname)s\n%(info.matchtype)s\n",
                        "-nomatchprintf",
                        "KO\nNone\nNone\n%(info.matchtype)s\n",
                        filename]

        fido_out = subprocess.run(fido_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        [status, puid, format_name, match_type] = fido_out.stdout.decode("utf-8").split('\n')[0:4]
        # need range because files like .txt generate multiple fido hits

        self.event = db_classes.PremisEvent(
            eventIdentifierType="UUID",
            eventIdentifierValue=str(uuid.uuid4()),
            eventType="format identification",
            eventDateTime=datetime.now(),
            eventDetail="program=fido",
            eventOutcome=match_type,
        )

        if status == "OK":
            self.format_name = format_name
            self.format_registry_key = puid
        else:
            self.format_name = "unknown"
            self.format_registry_key = None


def calculate_sha256(file):
    buffer_size = 1048576

    sha256 = hashlib.sha256()

    with open(file, 'rb') as f:
        while True:
            data = f.read(buffer_size)
            if not data:
                break
            sha256.update(data)

    return sha256.hexdigest()


class Checksums:
    def __init__(self, file):
        self.sha256 = calculate_sha256(file)

        self.event = db_classes.PremisEvent(
            eventIdentifierType="UUID",
            eventIdentifierValue=str(uuid.uuid4()),
            eventType="message digest calculation",
            eventDateTime=datetime.now()
        )


def ingest_file(file, db_session, ingest_record, partition_type):
    logger = logging.getLogger(__name__)

    filepath = os.fspath(file)
    filename = str(file.name)

    file_object = db_classes.PremisObject(
        contentLocationValue=filepath,
        objectIdentifierType="UUID",
        objectIdentifierValue=str(uuid.uuid4()),
        objectCategory="file",
        messageDigestAlgorithm="SHA256",
        messageDigest=""  # dummy value to prevent a not-null constraint violation
    )
    db_session.add(file_object)
    try:
        db_session.flush()
    except sqlalchemy.exc.IntegrityError:
        raise DuplicateIngestError

    logger.info('beginning ingest of %s', filepath)
    file_format = DetermineFormat(file)
    checksums = Checksums(file)

    file_object.messageDigest = checksums.sha256
    file_object.originalName = filename
    file_object.contentLocationType = partition_type  # TODO determine partition type dynamically
    file_object.file_size = os.path.getsize(filepath)
    file_object.formatName = file_format.format_name
    file_object.formatRegistryName = "PRONOM"
    file_object.formatRegistryKey = file_format.format_registry_key

    ingest_event = db_classes.PremisEvent(
        eventIdentifierType="UUID",
        eventIdentifierValue=str(uuid.uuid4()),
        eventType="ingestion",
        eventDateTime=datetime.now()
    )

    file_object.ingest = ingest_record
    file_object.events = [ingest_event, checksums.event, file_format.event]

    db_session.add_all([checksums.event, file_format.event])

    # run all format-specific ingests (NB https://stackoverflow.com/questions/28643534/)
    for i in dir(format_specific):
        item = getattr(format_specific, i)
        if callable(item) and i.startswith("ingest_"):
            item(file_object, db_session)
