#!/usr/bin/env python3
"""
Extract raw data and generate the files needed for generate.py.
"""

import csv
import json
import logging
import re

from pathlib import Path

_THIS_DIR = Path(__file__).absolute().parent

# Change the hard-coded paths below
# Input files
_ORDER_OUTLINE_ = _THIS_DIR / 'raw' / 'order-outline.txt'
_RAW_PAPER_SCHEDULE = _THIS_DIR / 'raw' / 'Detailed Schedule - oral sessions csv reformatted version.tsv'
_RAW_POSTER_IN_PERSON_SCHEDULE = _THIS_DIR / 'raw' / 'Detailed Schedule - Poster in-person sessions.tsv'
_RAW_POSTER_VIRTUAL_SCHEDULE = _THIS_DIR / 'raw' / 'Detailed Schedule - Posters virtual.tsv'
_RAW_FINDINGS_SCHEDULE = _THIS_DIR / 'raw' / 'Detailed Schedule - Findings in-person.tsv'
_RAW_PAPER_DETAILS = _THIS_DIR / 'raw' / 'Accepted papers main info for detailed program - Accepted_papers_main.tsv'
_RAW_FINDINGS_DETAILS = _THIS_DIR / 'raw' / 'Accepted papers main info for detailed program - Accepted_papers_findings.tsv'
_INDUSTRY_ALL = _THIS_DIR / 'raw' / 'Detailed Schedule - Industry.tsv'
_DEMO_POSTER = _THIS_DIR / 'raw' / 'Detailed Schedule - Demos.tsv'
_SRW_THESIS_PROPOSALS = _THIS_DIR / 'raw' / 'SRW Detailed Schedule - Day 2 formatted.tsv'
_SRW_POSTER_IN_PERSON_SCHEDULE = _THIS_DIR / 'raw' / 'SRW Detailed Schedule - SRW Poster in-person sessions.tsv'
_SRW_PAPER_DETAILS = _THIS_DIR / 'raw' / 'SRW Accepted papers info for detailed program - Accepted_papers_main.tsv'
# Output files
_ORDER_PREPROCESSED = _THIS_DIR / 'preprocessed' / 'order.txt'
_METADATA = _THIS_DIR / 'preprocessed' / 'metadata.tsv'

_TRACKS = [
'Industry', 'Demo',
'Computational Social Science and Cultural Analytics',
'Dialogue and Interactive Systems',
'Discourse and Pragmatics',
'Efficient Methods in NLP',
'Ethics, Bias, and Fairness',
'Human-Centered NLP',
'Information Extraction',
'Information Retrieval and Text Mining',
'Interpretability and Analysis of Models for NLP',
'Language Generation',
'Language Grounding to Vision, Robotics and Beyond',
'Language Resources and Evaluation',
'Linguistic Theories, Cognitive Modeling and Psycholinguistics',
'Machine Learning for NLP: Classification and Structured Prediction Models',
'Machine Learning for NLP: Language Modeling and Sequence to Sequence Models',
'Machine Translation',
'Multilinguality',
'NLP Applications',
'Phonology, Morphology and Word Segmentation',
'Question Answering',
'Semantics: Lexical Semantics',
'Semantics: Sentence-level Semantics and Textual Inference',
'Sentiment Analysis and Stylistic Analysis',
'Speech',
'Summarization',
'Syntax: Tagging, Chunking, and Parsing',
]
_TRACK_ALIASES = {
    'Dialogue and Interactive systems': 'Dialogue and Interactive Systems',
    'Efficient methods in NLP': 'Efficient Methods in NLP',
    'Ethics': 'Ethics, Bias, and Fairness',
    'Ethics, Bias and Fairness': 'Ethics, Bias, and Fairness',
    'Special Theme': 'Human-Centered NLP',
    'Information Retrieval': 'Information Retrieval and Text Mining',
    'Language Grounding to Vision': 'Language Grounding to Vision, Robotics and Beyond',
    'Language Resources': 'Language Resources and Evaluation',
    'Linguistic theories, Cognitive Modeling and Psycholinguistics':
        'Linguistic Theories, Cognitive Modeling and Psycholinguistics',
    'Linguistic Theories, Cognitive Modeling and Pycholinguistics':
        'Linguistic Theories, Cognitive Modeling and Psycholinguistics',
    'Machine Translation and Multilinguality': 'Machine Translation',
    'NLP Application': 'NLP Applications',
    'Speech and Multimodality': 'Speech',
    'Syntax: Tagging, Chunking and Parsing': 'Syntax: Tagging, Chunking, and Parsing',
}


def normalize_track(track, paper_id):
    if not track:
        return None
    if track in _TRACK_ALIASES:
        track = _TRACK_ALIASES[track]
    if track not in _TRACKS:
        logging.warning('Unrecognized track for %s: %s', paper_id, track)
    return track


class RawSchedule:

    def __init__(self):
        self.records = []

    def read_tsv(self, path, virtual=False):
        new_records = []
        with open(path) as fin:
            reader = csv.DictReader(fin, dialect=csv.excel_tab)
            for row in reader:
                record = {key: value.strip() for (key, value) in row.items() if key}
                if not record['Paper ID']:
                    continue
                record['Source'] = path.name
                record['Format'] = 'virtual' if virtual else 'in-person'
                track = record.get('Subtrack') or record.get('Track')
                record['Track'] = normalize_track(track, record['Paper ID'])
                new_records.append(record)
        logging.info('Read %d records from %s', len(new_records), path)
        self.records += new_records

    def check_duplicates(self):
        paper_id_to_records = {}
        for this_record in self.records:
            paper_id = this_record['Paper ID']
            for that_record in paper_id_to_records.get(paper_id, []):
                # One exception: virtual + in-person
                if [this_record.get('Format'), that_record.get('Format')].count('virtual') == 1:
                    continue
                logging.warning('Repeated ID in raw schedule files: %s', paper_id)
                logging.warning('    %s', that_record)
                logging.warning('    %s', this_record)
            paper_id_to_records.setdefault(paper_id, []).append(this_record)

    def search(self, query):
        for record in self.records:
            if all(record.get(key) == query[key] for key in query if not key.startswith('_')):
                if record.get('used'):
                    logging.warning('Reappearing schedule record: %s', record)
                record['used'] = True
                yield record

    def report_unused(self):
        for record in self.records:
            if not record.get('used'):
                logging.warning('Unused schedule record: %s', record)


class RawMetadata:

    def __init__(self):
        self.records = []

    def read_tsv(self, path, track_override=None, extra_metadata=None):
        new_records = []
        with open(path) as fin:
            reader = csv.DictReader(fin, dialect=csv.excel_tab)
            for row in reader:
                paper_id = row.get('Number') or row.get('Paper ID')
                paper_id = re.sub(r'SRW_(\d+)', r'\1-srw', paper_id)    # TODO: Remove this hack
                track = track_override or row.get('Subtrack') or row.get('Track')
                track = normalize_track(track, paper_id)
                record = {
                    'source': path.name,
                    'paper_id': paper_id,
                    'track': track,
                    'title': row['Title'],
                    'authors': row['Authors'],
                    }
                if extra_metadata:
                    record.update(extra_metadata)
                new_records.append(record)
        logging.info('Read %d metadata records from %s', len(new_records), path)
        self.records += new_records

    def check_duplicates(self):
        paper_id_to_records = {}
        for this_record in self.records:
            paper_id = this_record['paper_id']
            for that_record in paper_id_to_records.get(paper_id, []):
                logging.warning('Repeated ID in raw metadata files: %s', paper_id)
                logging.warning('    %s', that_record)
                logging.warning('    %s', this_record)
            paper_id_to_records.setdefault(paper_id, []).append(this_record)

    def mark_used(self, schedule_record):
        match = None
        for record in self.records:
            if record['paper_id'] == schedule_record['Paper ID']:
                match = record
                record.setdefault('used', []).append(schedule_record.get('Format', 'in-person'))
                if record['used'].count('in-person') > 1:
                    logging.warning('Re-queried metadata record: %s', record)
                if (record['track'] and schedule_record['Track'] and
                        record['track'] != schedule_record['Track']):
                    logging.warning('Mismatched track: %s', record['paper_id'])
                    logging.warning('   Metadata: %s | Schedule: %s',
                           record['track'], schedule_record['Track']) 
        return match

    def report_unused(self):
        for record in self.records:
            if not record.get('used'):
                logging.warning('Unused metadata record: %s', record)

    def dump_metadata(self, path):
        with open(path, 'w') as fout:
            print('paper_id\ttrack\ttitle\tauthors', file=fout)
            for record in self.records:
                print('{}\t{}\t{}\t{}'.format(
                    record['paper_id'],
                    record['track'],
                    record['title'],
                    record['authors']), file=fout)
        logging.info('Wrote %d metadata records to %s', len(self.records), path)


def dump_records(query, schedule_metadata_pairs, fout):
    # Grouped records
    if '_group_by' in query:
        subquery = dict(query)
        del subquery['_group_by']
        key_to_pairs = {}
        for pair in schedule_metadata_pairs:
            key = pair[0][query['_group_by']]
            key_to_pairs.setdefault(key, []).append(pair)
        for key in sorted(key_to_pairs):
            print(f'@ {key}', file=fout)
            dump_records(subquery, key_to_pairs[key], fout)
        return
    # Normal records
    for (schedule_record, metadata_record) in schedule_metadata_pairs:
        order_line = schedule_record['Paper ID']
        extra_info = {}
        if schedule_record.get('Paper Awards'):
            extra_info['award'] = schedule_record['Paper Awards'].replace(' ', '_')
        if 'type' in metadata_record:
            extra_info['type'] = metadata_record['type']
        if extra_info:
            order_line += ' ## ' + ' '.join(
                    '%{} {}'.format(key, value) for (key, value) in extra_info.items())
        print(order_line, file=fout)


def main():
    # set up the logging
    logging.basicConfig(format='%(levelname)s - %(message)s', level=logging.INFO)

    raw_schedule = RawSchedule()
    raw_metadata = RawMetadata()

    # Read data
    raw_schedule.read_tsv(_RAW_PAPER_SCHEDULE)
    raw_schedule.read_tsv(_RAW_POSTER_IN_PERSON_SCHEDULE)
    raw_schedule.read_tsv(_RAW_POSTER_VIRTUAL_SCHEDULE, virtual=True)
    raw_schedule.read_tsv(_RAW_FINDINGS_SCHEDULE)
    raw_schedule.read_tsv(_INDUSTRY_ALL)
    raw_schedule.read_tsv(_DEMO_POSTER)
    raw_schedule.read_tsv(_SRW_THESIS_PROPOSALS)
    raw_schedule.read_tsv(_SRW_POSTER_IN_PERSON_SCHEDULE)
    raw_schedule.check_duplicates()

    raw_metadata.read_tsv(_RAW_PAPER_DETAILS)
    raw_metadata.read_tsv(_RAW_FINDINGS_DETAILS, extra_metadata={'type': 'Findings'})
    raw_metadata.read_tsv(_INDUSTRY_ALL, track_override='Industry')
    raw_metadata.read_tsv(_DEMO_POSTER, track_override='Demo')
    raw_metadata.read_tsv(_SRW_PAPER_DETAILS)
    raw_metadata.check_duplicates()

    # Process the `order` file
    with open(_ORDER_OUTLINE_) as fin, open(_ORDER_PREPROCESSED, 'w') as fout:
        for line in fin:
            if line[0] == '{':
                query = json.loads(line)
                schedule_records = list(raw_schedule.search(query))
                schedule_metadata_pairs = [(record, raw_metadata.mark_used(record))
                        for record in schedule_records]
                dump_records(query, schedule_metadata_pairs, fout)
            else:
                fout.write(line)
    raw_schedule.report_unused()
    raw_metadata.report_unused()
    raw_metadata.dump_metadata(_METADATA)


if __name__ == '__main__':
    main()
