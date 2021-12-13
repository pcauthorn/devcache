import datetime
import inspect
import re
from dataclasses import dataclass, asdict
from typing import Any, List

import yaml
from dateutil.parser import parse

from gattr import gattr

parser_config = """
Context:
  default_date_format: "%M/%d/%y"

Builders:
    - category: optimus_filename
      parser: 
         class: FilenameParser
    - category: optimus_practice_location
      parser: 
        class: FullAddressParser
        options:
            aliased:
                full_address: veda_practice_address
      
    - category: optimus_billing_address
      parser:
        class: FullAddressParser
        options:
           aliased:
                full_address: veda_billing_address
      formatters: remove_chars(-)|upper
    - category: optimus_birth_date
      parser: 
        class: DateParser
        args: 
           datefmt: "%m-%d-%Y" 
        options:
            aliased:
               date_str: veda_birth_date
    - category: dirprint
      parser:
        class: TranslateParser
        args:
             options:
                  Y: ['Yes', 'Y', 'True', 'T']
                  N: ['No', 'N', 'False', 'F']
                  U: ['Unknown', 'U']

"""

config = yaml.safe_load(parser_config)

DATA = [{
    'veda_npi1': '123523434',
    'veda_specialty': 'Cardiology',
    'veda_practice_code': '42G',
    'firstname': 'Joe',
    'lastname': 'Jones',
    'veda_birth_date': '1-1-1955',
    'veda_medial_school_start_date': '2/2/1978',
    'veda_filename': 'hospital_1234',
    'veda_ignore': 'whateva',
    'dirprint': 'Unknown',
    'veda_billing_address': '101 Grand-Junction Blvd Houston Text 88209',
    'veda_practice_address': '42 East 93 Suite 100 New York NY 11022'
}]


def remove_chars(data_str, chars):
    result = data_str
    for c in chars:
        result = result.replace(c, '')
    return result

FORMATTERS = {
    'upper': str.upper,
    'lower': str.lower,
    'remove_chars': remove_chars,
    'datefmt': lambda d, f: d.strftime(f)
}

EPOCH = parse('1/1/1970')


class Model:
    pass


@dataclass
class FilenameModel(Model):
    office_type: str
    salesforce_id: str

    def get_output(self):
        return asdict(self)


@dataclass
class SaleforceUrlModel:
    url: str

    def get_output(self):
        return self.url


@dataclass
class AddressParserModel:
    full_address: str

    def get_output(self):
        return self.full_address


@dataclass
class TranslateParserModel:
    value: str

    def get_output(self):
        return self.value


class DateParser:
    def __init__(self, datefmt=None):
        self.datefmt = datefmt

    def parse(self, date_str):
        return datetime.datetime.strptime(date_str, self.datefmt)


class FilenameParser:
    def parse(self, veda_filename) -> FilenameModel:
        print(f'FilenameParser: {veda_filename}')
        office_type, salesforce_id = veda_filename.split('_')
        return FilenameModel(office_type=office_type, salesforce_id=salesforce_id)


class SalesforceInstance:
    def parse(self, veda_birthdate, optimus_filename):
        d = parse(veda_birthdate)
        if d > EPOCH:
            host = 'myinstance1'
        else:
            host = 'myinstance2'

        return SaleforceUrlModel(url=f'https://{host}-{optimus_filename.office_type}.salesforce.com')


class TranslateParser:
    def __init__(self, options):
        options = options or {}
        transposed = {}
        for k, vals in options.items():
            for v in vals:
                transposed[v] = k
        self.options = transposed

    def parse(self, dirprint):
        return self.options.get(dirprint)


class FullAddressParser:
    def parse(self, full_address):
        print(f'Geocode here!!')
        return AddressParserModel(full_address=full_address)


@dataclass
class OptimusEntity:
    parsed: Any
    formatters: Any


@dataclass
class Unresolved:
    parser: Any
    category: str
    method_keys: List[str]


def parse_entities(entities, config):
    unresolveds = []
    optimus_entities = []
    for entity in entities:
        optimus_entity = {}
        for builder_config in config['Builders']:
            parser_config = builder_config.get('parser')
            category = builder_config['category']
            if not parser_config:
                continue
            parser_class_name = parser_config['class']
            print(f'Processing {parser_class_name} for category {category}')
            args = parser_config.get('args', {})
            parser_class = globals()[parser_class_name]
            parser = parser_class(**args)
            signature = inspect.signature(parser.parse)
            method_args = {}
            unresolved = None
            aliases = gattr(parser_config, 'options', 'aliased', default={})
            for param in signature.parameters:
                aliased = aliases.get(param, param)
                if aliased in entity:
                    method_args[param] = entity[aliased]
                elif param in optimus_entity:
                    method_args[param] = optimus_entity[aliased]
                elif param.startswith('optimus'):
                    unresolved = Unresolved(parser, builder_config['category'], list(signature.parameters.keys()))
                    break
                else:
                    raise TypeError(f'Could not resolve {param} for {parser_config["class"]}')
            if unresolved:
                unresolveds.append(unresolved)
            else:
                optimus_entity[builder_config['category']] = OptimusEntity(parsed=parser.parse(**method_args),
                                                                           formatters=builder_config.get('formatters'))
        next_unresolveds = []
        while True:
            resolved = 0
            if not unresolveds:
                break
            for potential in unresolveds:
                method_args = {}
                for param in potential.method_keys:
                    if param in entity:
                        method_args[param] = entity[param]
                    elif param in optimus_entity:
                        method_args[param] = optimus_entity[param]
                    else:
                        next_unresolveds.append(potential)
                        break
                else:
                    resolved += 1
                    optimus_entity[potential.category] = potential.parser.parse(*method_args)

            if resolved == 0:
                raise TypeError(f'Unable to resolve args for {unresolveds}.  Circular dependency not or found params?')
        optimus_entities.append(optimus_entity)

    return optimus_entities


def apply_formats(formatters, optimus_data):
    if not formatters:
        return optimus_data
    result = optimus_data
    for formatter in [f.strip() for f in formatters.split('|')]:
        match = re.findall(r'(.*)\((.*?)\)', formatter)
        formatter_args = []
        if match:
            formatter = match[0][0]
            formatter_args = match[0][1].split(',')
        else:
            formatter = formatter
        format_method = FORMATTERS[formatter]
        result = format_method(result, *formatter_args)
    return result


def make_output(optimus_entities):
    result = []
    for optimus_entity in optimus_entities:
        data = {}
        for category, entity in optimus_entity.items():
            formatters = entity.formatters
            output = entity.parsed
            if hasattr(output, 'get_output'):
                output = output.get_output()
            if not isinstance(output, dict):
                data[category] = apply_formats(formatters, output)
            else:
                for k, v in output.items():
                    # TODO:
                    # Formatters could be a dict to the keys in this dict
                    data[f'{category}#{k}'] = apply_formats(formatters, v)
        result.append(data)
    return result


if __name__ == '__main__':
    from pprint import pprint

    parsed = parse_entities(DATA, config)
    pprint(parsed)
    output = make_output(parsed)
    pprint(output)
