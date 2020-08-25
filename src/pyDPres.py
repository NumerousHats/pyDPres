from pathlib import Path
import os
import configparser
import logging
from logging.config import dictConfig
from session import *
import subprocess
from datetime import datetime, timedelta

import click
from appdirs import AppDirs
import sqlalchemy as sqla
from sqlalchemy import exc

from db_classes import *
from ingest import *
from fixity import *

DB_VERSION = "0.1"


def create_new_database(filename):
    engine = sqla.create_engine("sqlite:///{}".format(filename))
    Session.configure(bind=engine)
    db_classes.Base.metadata.create_all(engine)
    session = Session()
    info = db_classes.PyDPresInfo(info_name="version", info_value=DB_VERSION)
    session.add(info)
    session.commit()
    session.close()


@click.group()
@click.option('--dbfile', help="specify the SQLite database file to use")
@click.option('--quiet', is_flag=True, help='turn off logging to stderr')
@click.pass_context
def cli(context, dbfile, quiet):
    """
    `pyDPres` is a tool for checksum/hash calculation, fixity checking, format identification, and
    generation of preservation metadata.  It can be run on the command line or as a cron job.

    Preservation metadata are saved in a PREMIS-compliant sqlite file in a configurable location.
    Run `pyDPres configure` to set up.
    """

    context.ensure_object(dict)

    dirs = AppDirs("pyDPres", "UHEC")
    user_data_dir = Path(dirs.user_data_dir)
    context.obj["user_data_dir"] = user_data_dir
    config_file = user_data_dir / "pyDPres-config.ini"
    config = configparser.ConfigParser()

    context.obj["has_config"] = False
    if config_file.exists():
        try:
            config.read(config_file)
            context.obj["config_dbfile"] = config["DEFAULT"]["DEFAULT_DB"]
            context.obj["file_logging"] = True if config["DEFAULT"]["FILE_LOGGING"] == "True" else False
            context.obj["fixity_interval"] = config["DEFAULT"]["FIXITY_INTERVAL"]
            context.obj["partition_type"] = config["DEFAULT"]["PARTITION_TYPE"]
            context.obj["has_config"] = True
        except (KeyError, configparser.Error):
            pass

    if context.obj["has_config"]:
        logging_config = dict(
            version=1,
            formatters={
                'verbose': {
                    'format': "%(asctime)s %(name)-12s %(levelname)-8s [%(filename)s:%(funcName)20s] %(message)s"
                },
                'full': {
                    'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
                },
                'simple': {
                    'format': '%(levelname)s %(message)s'
                }
            },
            handlers={
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'simple',
                    'level': logging.INFO
                },
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'formatter': 'verbose',
                    'filename': user_data_dir / "pyDPres.log",
                    'maxBytes': 1024,
                    'level': logging.DEBUG,
                }
            },
            root={
                'level': logging.DEBUG,
            }
        )

        handler_list = []

        if not quiet:
            handler_list.append('console')

        if context.obj["file_logging"]:
            handler_list.append('file')

        logging_config['root']['handlers'] = handler_list

        dictConfig(logging_config)
        logger = logging.getLogger(__name__)

        if dbfile:
            if not os.path.isfile(dbfile):
                click.echo("The specified file does not exist.")
                click.confirm('Would you like to create it?', abort=True, default=True)
                create_new_database(dbfile)
        else:
            dbfile = context.obj["config_dbfile"]

        engine = sqla.create_engine("sqlite:///{}".format(dbfile))
        Session.configure(bind=engine)
        session = Session()
        try:
            db_version, = session.query(db_classes.PyDPresInfo.info_value).filter_by(info_name="version").one()
            if db_version != DB_VERSION:
                raise click.ClickException('{} was created with an incompatible version of pyDPres.'.format(dbfile))
        except (exc.OperationalError, exc.DatabaseError):
            raise click.ClickException('{} is not a valid pyDPres database.'.format(dbfile))

        context.obj["db_session"] = session


@cli.command()
@click.pass_context
def configure(context):
    """
    Set pyDPres configurations
    """

    if context.obj["has_config"]:
        click.echo("\nThis operation may change the default database and render previous ingest data inaccessible.")
        click.confirm('Do you really want to do this?', abort=True, default=True)

    user_dir = Path(context.obj["user_data_dir"])
    user_dir.mkdir(parents=True, exist_ok=True)

    old_default_db = user_dir / "pyDPres.sqlite" if not context.obj["has_config"] \
        else context.obj["config_dbfile"]
    default_db = click.prompt("\nSet default database", default=old_default_db)

    if not os.path.isfile(default_db):
        # file is not there, so create it
        create_new_database(default_db)
    else:
        # file is there. check if it's valid, if not, confirm before delete and recreate
        engine = sqla.create_engine("sqlite:///{}".format(default_db))
        Session.configure(bind=engine)
        session = Session()
        try:
            db_version, = session.query(db_classes.PyDPresInfo.info_value).filter_by(info_name="version").one()
            if db_version != DB_VERSION:
                click.echo('\n{} was created with an incompatible version of pyDPres.'.format(default_db))
                click.confirm('Would you like to delete it and generate a new, empty database?', abort=True)

                session.close()
                os.remove(default_db)
                create_new_database(default_db)
        except (exc.OperationalError, exc.DatabaseError):
            click.echo('\n{} is not a valid pyDPres database file.'.format(default_db))
            click.confirm('Would you like to delete it and generate a new, empty database?', abort=True)

            session.close()
            os.remove(default_db)
            create_new_database(default_db)

    file_logging = click.confirm("\nShould logging data be saved to {}?".format(user_dir / "pyDPres.log"), default=True)

    old_fixity_interval = 7 if not context.obj["has_config"] else context.obj["fixity_interval"]
    fixity_interval = click.prompt("\nWait how many days between fixity checks?", default=old_fixity_interval)

    old_partition_type = "NTFS" if not context.obj["has_config"] else context.obj["partition_type"]
    click.echo("\npyDPres does not currently determine the disk partition type 'on the fly'.")
    partition_type = click.prompt("What is your disk partition type?", default=old_partition_type)

    config = configparser.ConfigParser()
    config['DEFAULT'] = {
        "DEFAULT_DB": os.fspath(default_db),
        "FILE_LOGGING": file_logging,
        "FIXITY_INTERVAL": fixity_interval,
        "PARTITION_TYPE": partition_type
    }
    config_file = user_dir / "pyDPres-config.ini"
    with open(config_file, 'w') as configfile:
        config.write(configfile)

    click.echo("\npyDPres is now configured. You may now run 'pyDPres [command]'")


@cli.command()
@click.argument('paths', nargs=-1)
@click.option('--dry-run', is_flag=True, help="List files without actually ingesting them")
@click.option('--stdin', is_flag=True, help="Read filenames from STDIN")
@click.option('--note', help="Optional description of ingest")
@click.pass_context
def ingest(context, paths, dry_run, stdin, note):
    """
    Ingest files for preservation
    """

    if not context.obj["has_config"]:
        raise click.ClickException("Improper configuration detected. Run 'pyDPres configure' to set up.")

    fido_command = ["fido", "-matchprintf",
                    "OK\n%(info.puid)s\n%(info.formatname)s\n%(info.matchtype)s\n"]

    try:
        fido_out = subprocess.run(fido_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise click.ClickException("External program 'fido' not found. You will not be able to run ingests.")

    if fido_out.returncode != 0:
        raise click.ClickException("You must install the current master branch of 'fido' from Github to run ingests.")

    logger = logging.getLogger(__name__)
    db_session = context.obj["db_session"]

    if stdin:  # TODO
        click.echo("`--stdin` option is not yet implemented")
        return

    ingest_record = db_classes.PyDPresIngest(ingest_start_time=datetime.now())
    if note:
        ingest_record.ingest_note = note
    db_session.add(ingest_record)

    for path in paths:
        for root, dirs, files in os.walk(path):
            for file in [os.path.join(root, name) for name in files]:
                filepath = Path(file).resolve()
                if filepath.is_file() and not filepath.is_symlink():
                    if dry_run:
                        click.echo(os.fspath(filepath))
                    else:
                        try:
                            ingest_file(filepath, db_session, ingest_record, context.obj["partition_type"])
                            ingest_record.ingest_end_time = datetime.now()
                            db_session.commit()
                        except DuplicateIngestError:
                            logger.warning('%s already ingested', file)
                            db_session.rollback()
                        except:
                            db_session.rollback()
                            db_session.close()
                            raise

    db_session.close()


@cli.command()
@click.pass_context
@click.option('--age', type=int,
              help="Ignore files that were fixity checked more recently than this number of days")
def fixity(context, age):
    """
    Perform a fixity check
    """
    """
    Files are checked in order of the longest time since last fixity check.
    File objects that have a "fixity check" or "ingestion" event less than "age" days ago will not be checked.
    """

    if not context.obj["has_config"]:
        raise click.ClickException("Improper configuration detected. Run 'pyDPres configure' to set up.")

    db_session = context.obj["db_session"]

    logger = logging.getLogger(__name__)
    logger.info("starting fixity run")

    if age is None:
        age = int(context.obj["fixity_interval"])
    datetime_cutoff = datetime.now() - timedelta(days=age)

    for premis_object, last_checked in db_session.query(PremisObject, sqla.func.max(PremisEvent.eventDateTime)).\
            join(PremisEvent).\
            filter(sqla.or_(PremisEvent.eventType == "ingestion", PremisEvent.eventType == "fixity check")).\
            filter(PremisObject.objectCategory == "file").\
            group_by(PremisObject.object_id).\
            order_by(PremisEvent.eventDateTime).\
            all():
        if last_checked < datetime_cutoff:
            try:
                event = check_object_fixity(premis_object)
                db_session.add(event)
                db_session.commit()
            except:
                db_session.rollback()
                db_session.close()
                logger.error("got exception in fixity check of {}".format(premis_object.contentLocationValue))
                raise

    db_session.close()
    logger.info("completed fixity run")


@cli.command()
@click.pass_context
@click.argument('outfile', nargs=1)
def report(context, outfile):
    """
    Export metadata and fixity information to a CSV file
    """

    if not context.obj["has_config"]:
        raise click.ClickException("Improper configuration detected. Run 'pyDPres configure' to set up.")

    db_session = context.obj["db_session"]

    click.echo("not yet implemented")  # TODO


if __name__ == "__main__":
    cli()
