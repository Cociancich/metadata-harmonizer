#!/usr/bin/env python3
"""
This script contains tools to access, download and parse Metadata stored in Markdown in a gitlab repository.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 3/3/23
"""
import os
import urllib
import ssl
import rich
import pandas as pd
import json

emso_metadata_url = "https://gitlab.emso.eu/Martinez/emso-metadata-specification/-/raw/v0.1/EMSO_metadata.md"
oceansites_codes_url = "https://gitlab.emso.eu/Martinez/emso-metadata-specification/-/raw/v0.1/OceanSites_codes.md"
emso_codes_url = "https://gitlab.emso.eu/Martinez/emso-metadata-specification/-/raw/v0.1/EMSO_codes.md"

sdn_vocab_p01 = "https://vocab.nerc.ac.uk/collection/P01/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_p02 = "https://vocab.nerc.ac.uk/collection/P01/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_p06 = "https://vocab.nerc.ac.uk/collection/P06/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l22 = "https://vocab.nerc.ac.uk/collection/L22/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l05 = "https://vocab.nerc.ac.uk/collection/L22/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l06 = "https://vocab.nerc.ac.uk/collection/L22/current/?_profile=nvs&_mediatype=application/ld+json"
standard_names = "https://vocab.nerc.ac.uk/standard_name/?_profile=nvs&_mediatype=application/ld+json"

edmo_codes = "https://edmo.seadatanet.org/sparql/sparql?query=SELECT%20%3Fs%20%3Fp%20%3Fo%20WHERE%20%7B%20%0D%0A%0" \
             "9%3Fs%20%3Fp%20%3Fo%20%0D%0A%7D%20LIMIT%201000000&accept=application%2Fjson"



def process_markdown_file(file) -> (dict, dict):
    """
    Processes the Markdown file and parses their tables. Every table is returned as a pandas dataframe.
    :returns: a dict wher keys are table titles and values are dataframes with the info
    """
    with open(file) as f:
        lines = f.readlines()

    title = ""
    tables = {}
    in_table = False
    lines += "\n"  # add an empty line to force table end
    for line in lines:
        if line.startswith("#"):  # store the title
            title = line.strip().replace("#", "").strip()

        elif not in_table and line.startswith("|"):  # header of the table
            table = {}
            headers = line.strip().split("|")[1:-1]  # first and last are empty
            headers = [h.strip() for h in headers]

            for header in headers:
                table[header] = []
            in_table = True
            rich.print(f"parsing Markdown table [cyan]'{title}'[/cyan]...", end="")

        elif in_table and not line.startswith("|"):  # end of the table
            in_table = False
            tables[title] = pd.DataFrame(table)  # store the metadata as a DataFrame
            rich.print("[green]done")

        elif line.startswith("|---"):  # skip the title and body separator (|----|---|---|)
            continue

        elif line.startswith("|"):  # process the row
            fields = line.strip().replace(" ", "").split("|")[1:-1]
            for i in range(len(fields)):
                if fields[i] in ["false", "False"]:
                    table[headers[i]].append(False)
                elif fields[i] in ["true", "True"]:
                    table[headers[i]].append(True)
                else:
                    table[headers[i]].append(fields[i])
    return tables


def download_files(tasks, force_download=False):
    if len(tasks) == 1:
        return None

    rich.print("Downloading files...")
    for url, file, name in tasks:
        if os.path.isfile(file) and not force_download:
            rich.print(f"     [dark_grey]{name} already downloaded")
        else:
            rich.print(f"    downloading [cyan]'{name}'[/cyan]...", end="")
            urllib.request.urlretrieve(url, file)
            rich.print("[green]done!")

    rich.print("[green]All files downloaded!")


def get_sdn_jsonld_ids(file):
    with open(file) as f:
        data = json.load(f)

    ids = []
    for element in data["@graph"]:
        if "identifier" in element.keys():
            ids.append(element["identifier"])
    return ids


def get_standard_names(file):
    with open(file) as f:
        data = json.load(f)

    names = []
    for element in data["@graph"][1:]:
        if "prefLabel" in element.keys() and "@value" in element["prefLabel"].keys():
            names.append(element["prefLabel"]["@value"])
    return names


def get_edmo_codes(file):
    with open(file) as f:
        data = json.load(f)

    codes = []
    for element in data["results"]["bindings"]:
        try:
            code = element["s"]["value"]
            code = int(code.split("/")[-1])
            if code not in codes:
                codes.append(code)
        except KeyError:
            continue

    codes = sorted(codes)
    return codes


class EmsoMetadata:
    def __init__(self, force_update=False):
        self.__folder = ".emso"
        os.makedirs(".emso", exist_ok=True)  # create a conf dir to store Markdown and other stuff
        ssl._create_default_https_context = ssl._create_unverified_context

        self.emso_metadata_file = os.path.join(self.__folder, "EMSO_metadata.md")
        self.oceansites_file = os.path.join(self.__folder, "OceanSites_codes.md")
        self.emso_sites_file = os.path.join(self.__folder, "EMSO_codes.md")
        self.sdn_vocab_p01_file = os.path.join(self.__folder, "sdn_vocab_p01.json")
        self.sdn_vocab_p02_file = os.path.join(self.__folder, "sdn_vocab_p02.json")
        self.sdn_vocab_p06_file = os.path.join(self.__folder, "sdn_vocab_p06.json")
        self.sdn_vocab_l05_file = os.path.join(self.__folder, "sdn_vocab_l05.json")
        self.sdn_vocab_l06_file = os.path.join(self.__folder, "sdn_vocab_l06.json")
        self.sdn_vocab_l22_file = os.path.join(self.__folder, "sdn_vocab_l22.json")
        self.standard_names_file = os.path.join(self.__folder, "standard_names.json")
        self.edmo_codes_file = os.path.join(self.__folder, "edmo_codes.json")

        tasks = [
            [emso_metadata_url, self.emso_metadata_file, "EMSO metadata"],
            [oceansites_codes_url, self.oceansites_file, "OceanSites"],
            [emso_codes_url, self.emso_sites_file, "EMSO codes"],
            [sdn_vocab_p01, self.sdn_vocab_p01_file, "SDN Vocab P01"],
            [sdn_vocab_p02, self.sdn_vocab_p02_file, "SDN Vocab P02"],
            [sdn_vocab_p06, self.sdn_vocab_p06_file, "SDN Vocab P06"],
            [sdn_vocab_l05, self.sdn_vocab_l05_file, "SDN Vocab L05"],
            [sdn_vocab_l06, self.sdn_vocab_l06_file, "SDN Vocab L06"],
            [sdn_vocab_l22, self.sdn_vocab_l22_file, "SDN Vocab L22"],
            [standard_names, self.standard_names_file, "CF standard names"],
            [edmo_codes, self.edmo_codes_file, "EDMO codes"]
        ]

        download_files(tasks)

        tables = process_markdown_file(self.emso_metadata_file)
        self.global_attr = tables["Global Attributes"]
        self.variable_attr = tables["Variable Attributes"]

        tables = process_markdown_file(self.oceansites_file)
        self.sensor_mount = tables["Sensor Mount"]
        self.sensor_orientation = tables["Sensor Orientation"]

        tables = process_markdown_file(self.emso_sites_file)
        self.emso_regional_facilities = tables["EMSO Regional Facilities"]

        rich.print("Loading SeaDataNet vocabularies...", end="")
        self.sdn_vocabs = {
            "P01": get_sdn_jsonld_ids(self.sdn_vocab_p01_file),
            "P02": get_sdn_jsonld_ids(self.sdn_vocab_p02_file),
            "P06": get_sdn_jsonld_ids(self.sdn_vocab_p06_file),
            "L05": get_sdn_jsonld_ids(self.sdn_vocab_l05_file),
            "L06": get_sdn_jsonld_ids(self.sdn_vocab_l06_file),
            "L22": get_sdn_jsonld_ids(self.sdn_vocab_l22_file)
        }
        self.standard_names = get_standard_names(self.standard_names_file)
        self.edmo_codes = get_edmo_codes(self.edmo_codes_file)

