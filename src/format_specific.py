"""Custom ingest and bitstream fixity checking for specific file types"""

from datetime import datetime
import io
import csv
import subprocess
import uuid
import logging

import db_classes


def get_bwf_tech(file):
    tech_csv = subprocess.check_output(["bwfmetaedit", "--accept-nopadding",
                                        "--out-tech", "--MD5-Verify", file],
                                       universal_newlines=True,
                                       stderr=subprocess.DEVNULL)
    f = io.StringIO(tech_csv)
    reader = csv.DictReader(f, delimiter=',')
    tech = next(reader)
    return tech


def get_bwf_core(file):
    core_csv = subprocess.check_output(["bwfmetaedit", "--accept-nopadding",
                                        "--out-core", file],
                                       universal_newlines=True,
                                       stderr=subprocess.DEVNULL)
    f = io.StringIO(core_csv)
    reader = csv.DictReader(f, delimiter=',')
    core = next(reader)
    return core


def ingest_wave(file_object, session):
    wave_file_keys = ["fmt/141", "fmt/143", "fmt/703", "fmt/704", "fmt/709", "fmt/712",
                      "fmt/713", "fmt/6", "fmt/2", "fmt/1", "fmt/527", "fmt/705", "fmt/706",
                      "fmt/707", "fmt/708", "fmt/710", "fmt/711"]

    if file_object.formatRegistryKey not in wave_file_keys:
        return

    logger = logging.getLogger(__name__)
    logger.info('beginning bitstream ingest of %s', file_object.originalName)

    file = file_object.contentLocationValue
    try:
        bwf_tech_md = get_bwf_tech(file)
    except FileNotFoundError:
        logger.error("'bwfmetaedit' not found. Cannot do WAVE bitstream ingests.")
        return

    if bwf_tech_md["Errors"] == "":
        digest_event = db_classes.PremisEvent(
            eventIdentifierType="UUID",
            eventIdentifierValue=str(uuid.uuid4()),
            eventType="message digest calculation",
            eventDateTime=datetime.now()
        )
        if bwf_tech_md["Information"] == "MD5, no existing MD5 chunk":
            logger.warning('{} has no stored MD5'.format(file))
            file_object.properties.append(db_classes.PremisSignificantProperties(
                significantPropertiesType="HasEmbeddedDigest",
                significantPropertiesValue="False"))
        else:
            file_object.properties.append(db_classes.PremisSignificantProperties(
                significantPropertiesType="HasEmbeddedDigest",
                significantPropertiesValue="True"))

        if bwf_tech_md["Information"] == "MD5, failed verification":
            logger.warning("{} MD5 verification failed".format(file))

        ingest_event = db_classes.PremisEvent(
            eventIdentifierType="UUID",
            eventIdentifierValue=str(uuid.uuid4()),
            eventType="ingestion",
            eventDateTime=datetime.now()
        )

        bitstream_object = db_classes.PremisObject(
            objectIdentifierType="UUID",
            objectIdentifierValue=str(uuid.uuid4()),
            objectCategory="bitstream",
            messageDigestAlgorithm="MD5",
            messageDigest=bwf_tech_md["MD5Generated"],
            formatName="PCM audio",
            ingest_id=file_object.ingest_id,
            relationshipType="structural",
            relationshipSubType="is Part Of"
        )

        bitstream_object.events = [ingest_event, digest_event]

        file_object.relationshipType = "structural"
        file_object.relationshipSubType = "has Part"
        file_object.related_objects = [bitstream_object]

        file_object.relatedObject_id = bitstream_object.object_id

        property_types = ["Duration", "Channels", "SampleRate", "BitPerSample"]
        properties = []
        for property in property_types:
            properties.append(db_classes.PremisSignificantProperties(
                significantPropertiesType=property,
                significantPropertiesValue=bwf_tech_md[property]))

        bwf_core_md = get_bwf_core(file)

        if bwf_core_md["OriginationDate"] and bwf_core_md["OriginationTime"]:
            properties.append(db_classes.PremisSignificantProperties(
                significantPropertiesType="Origination",
                significantPropertiesValue=bwf_core_md["OriginationDate"] + "T" + bwf_core_md["OriginationTime"]
            ))
        if bwf_core_md["Description"]:
            properties.append(db_classes.PremisSignificantProperties(
                significantPropertiesType="Description",
                significantPropertiesValue=bwf_core_md["Description"]
            ))
        if bwf_core_md["ICRD"]:
            properties.append(db_classes.PremisSignificantProperties(
                significantPropertiesType="CreationDate",
                significantPropertiesValue=bwf_core_md["ICRD"]
            ))
        if bwf_core_md["INAM"]:
            properties.append(db_classes.PremisSignificantProperties(
                significantPropertiesType="Title",
                significantPropertiesValue=bwf_core_md["INAM"]
            ))
        file_object.properties.extend(properties)

        session.add_all([digest_event, ingest_event, bitstream_object])
    else:
        logger.error("bitstream ingest for {} failed: {}".format(file, bwf_tech_md["Errors"]))


def fixity_wave(file_object):
    logger = logging.getLogger(__name__)
    file = file_object.contentLocationValue

    try:
        bwf_tech_md = get_bwf_tech(file)
    except FileNotFoundError:
        logger.error("'bwfmetaedit' not found. Cannot do WAVE bitstream fixity check.")
        return

    related_bitstream = file_object.related_objects[0]

    if bwf_tech_md["Errors"] == "":
        if bwf_tech_md["Information"] == "MD5, verified":
            event_outcome = "OK"
        elif bwf_tech_md["Information"] == "MD5, failed verification":
            event_outcome = "Failed"
        elif bwf_tech_md["Information"] == "MD5, no existing MD5 chunk":
            old_digest = related_bitstream.messageDigest
            if old_digest == bwf_tech_md["MD5Generated"]:
                event_outcome = "OK"
            else:
                event_outcome = "Failed"
        else:
            logger.error("unexpected bwfmetaedit information string {}".format(bwf_tech_md["Information"]))
            return

        fixity_event = db_classes.PremisEvent(
            eventIdentifierType="UUID",
            eventIdentifierValue=str(uuid.uuid4()),
            eventType="fixity check",
            eventOutcome=event_outcome,
            eventDateTime=datetime.now()
        )

        fixity_event.premis_object = related_bitstream

    else:
        logger.error("bitstream fixity check of {} failed: {}".format(file, bwf_tech_md["Errors"]))

