import logging
import uuid
from datetime import datetime

import db_classes
import ingest
import format_specific


def check_object_fixity(premis_object):
    logger = logging.getLogger("pyDPres")
    file = premis_object.contentLocationValue
    logger.debug("start fixity check of {}".format(file))

    try:
        new_hash = ingest.calculate_sha256(file)
        if new_hash == premis_object.messageDigest:
            outcome = "OK"
            logger.debug("{} fixity verified".format(file))
        else:
            outcome = "Failed"
            logger.warning("{} fixity check failed".format(file))

            # perhaps fixity failure is due to update of embedded metadata: check bitstream fixity
            #
            # run all custom fixity checks (NB https://stackoverflow.com/questions/28643534/)
            for i in dir(format_specific):
                item = getattr(format_specific, i)
                if callable(item) and i.startswith("fixity_"):
                    item(premis_object)
    except FileNotFoundError:
        logger.warning("{} is missing".format(file))
        outcome = "Missing"

    fixity_event = db_classes.PremisEvent(
        eventIdentifierType="UUID",
        eventIdentifierValue=str(uuid.uuid4()),
        eventType="fixity check",
        eventDateTime=datetime.now(),
        eventOutcome=outcome
    )
    fixity_event.premis_object = premis_object

    return premis_object
