# pyDPres

A lightweight tool for the utter basics of digital preservation


_for Python 3.6 or above_

`pyDPres` is a tool for checksum/hash calculation, fixity checking, format identification, and generation of preservation metadata. It is intended for situations where more powerful tools such as [Archivematica](http://archivematica.org) or full-blown digital repositories are not needed or cannot be used due to resource or IT limitations. 

Unlike full digital preservation systems,`pyDPres` does not provide appraisal tools, format normalization, migration, or virus checking/quarantine. It also makes no explicit effort to be compliant with the [OAIS model](https://en.wikipedia.org/wiki/Open_Archival_Information_System). 

Instead, it is inspired by fixity tools such as "[fixity checker](https://github.com/tingletech/fixity_checker)" and AV Preserve's "[fixity](https://www.weareavp.com/products/fixity/)" software. However, it goes beyond them by doing format identification and storing the resulting preservation metadata in an open-format [PREMIS](http://www.loc.gov/standards/premis/v3/)–compliant database. In addition, `pyDPres` can, with some Python programming ability, be extended to provide custom preservation metadata for specific file types and bitstreams based on local repository needs.

`pyDPres` is intended for Unix-like systems, but could potentially be run on other platforms. It can be run on the command line or as a `cron` job.

Preservation metadata is stored in an sqlite database file using a restricted subset of the PREMIS metadata schema.

## Installation
`pip install git+git://github.com/openpreserve/fido.git#egg=fido` 

(`pyDPres` requires a version of `fido` containing the bug fix [PR#136](https://github.com/openpreserve/fido/pull/136). As of 2018-12, this pull request has not been incorporated into a release, therefore installation of the latest master branch is required.)

To use the BWF bitstream ingest feature, the `bwfmetaedit` command line tool must also be installed.



## Usage

### `pyDPres configure`
Define and create the default database, and set default values for program configuration.

### `pyDPres ingest [paths]`
Recursively ingest all files in the listed paths. Links and files that have already been ingested are ignored. 

During the ingest process, each file is subjected to PRONOM format identification using [fido](http://openpreservation.org/technology/products/fido/), SHA256 hash calculation, and the generation of any additional custom preservation metadata (as shipped, it generates bitstream objects for WAVE file PCM data chunks and calculates their MD5 hashes using `bwfmetaedit`).

### `pyDPres fixity [--age]`

Run a fixity check of all ingested files. File objects that have the longest elapsed time since their ingest or last fixity check are checked first. By default, file objects that have a fixity check or ingestion event less than a configurable maximum age are ignored. This behavior can be changed by specifying an `--age` argument (e.g. `pyDPres fixity --age 14` to only check files where 14 days have gone by since their last fixity check, or `pyDPres fixity --age 0` to fixity check all files unconditionally).

### `pyDPres report "filename"`
Generate a CSV file listing all ingested files, their vital statistics, and the date and outcome of the last fixity check.
 
[not yet implemented]