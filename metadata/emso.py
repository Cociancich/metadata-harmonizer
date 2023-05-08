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
import ssl
import rich
import pandas as pd
import json
import time
from .utils import download_files

emso_version = "develop"
#emso_version = "v0.1"


# List of URLs
emso_metadata_url = f"https://gitlab.emso.eu/Martinez/emso-metadata-specification/-/raw/{emso_version}/EMSO_metadata.md"
oceansites_codes_url = f"https://gitlab.emso.eu/Martinez/emso-metadata-specification/-/raw/{emso_version}/OceanSites_codes.md"
emso_codes_url = f"https://gitlab.emso.eu/Martinez/emso-metadata-specification/-/raw/{emso_version}/EMSO_codes.md"

sdn_vocab_p01 = "https://vocab.nerc.ac.uk/downloads/publish/P01.json"
sdn_vocab_p02 = "https://vocab.nerc.ac.uk/collection/P02/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_p06 = "https://vocab.nerc.ac.uk/collection/P06/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_p07 = "https://vocab.nerc.ac.uk/collection/P07/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l05 = "https://vocab.nerc.ac.uk/collection/L05/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l06 = "https://vocab.nerc.ac.uk/collection/L06/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l22 = "https://vocab.nerc.ac.uk/collection/L22/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l35 = "https://vocab.nerc.ac.uk/collection/L35/current/?_profile=nvs&_mediatype=application/ld+json"
# standard_names = "https://vocab.nerc.ac.uk/standard_name/?_profile=nvs&_mediatype=application/ld+json"

edmo_codes = "https://edmo.seadatanet.org/sparql/sparql?query=SELECT%20%3Fs%20%3Fp%20%3Fo%20WHERE%20%7B%20%0D%0A%0" \
             "9%3Fs%20%3Fp%20%3Fo%20%0D%0A%7D%20LIMIT%201000000&accept=application%2Fjson"

spdx_licenses_github = "https://raw.githubusercontent.com/spdx/license-list-data/main/licenses.md"


def process_markdown_file(file) -> (dict, dict):
    """
    Processes the Markdown file and parses their tables. Every table is returned as a pandas dataframe.
    :returns: a dict wher keys are table titles and values are dataframes with the info
    """
    with open(file, encoding="utf-8") as f:
        lines = f.readlines()

    title = ""
    tables = {}
    in_table = False
    lines += "\n"  # add an empty line to force table end
    linenum = 0
    for line in lines:
        line = line.strip()
        linenum += 1
        if line.startswith("#"):  # store the title
            title = line.strip().replace("#", "").strip()

        elif not in_table and line.startswith("|"):  # header of the table
            if not line.endswith("|"):
                line += "|"  # fix tables not properly formatted
            table = {}
            headers = line.strip().split("|")
            headers = [h.strip() for h in headers][1:-1]

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
            if not line.endswith("|"):
                line += "|"  # fix tables not properly formatted
            fields = [f.strip() for f in line.split("|")[1:-1]]
            for i in range(len(fields)):
                if fields[i] in ["false", "False"]:
                    table[headers[i]].append(False)
                elif fields[i] in ["true", "True"]:
                    table[headers[i]].append(True)
                else:
                    table[headers[i]].append(fields[i])
    return tables


def get_sdn_jsonld_ids(file):
    with open(file, encoding="utf-8") as f:
        data = json.load(f)
    ids = []
    for element in data["@graph"]:
        if "identifier" in element.keys():
            ids.append(element["identifier"])
    return ids


def get_sdn_jsonld_pref_label(file):
    with open(file, encoding="utf-8") as f:
        data = json.load(f)

    names = []
    for element in data["@graph"][1:]:
        if "prefLabel" in element.keys() and "@value" in element["prefLabel"].keys():
            names.append(element["prefLabel"]["@value"])
    return names


def get_sdn_jsonld_uri(file):
    with open(file, encoding="utf-8") as f:
        data = json.load(f)

    names = []
    for element in data["@graph"][1:]:
        if "@id" in element.keys():
            names.append(element["@id"])
    return names


def get_edmo_codes(file):
    with open(file, encoding="utf-8") as f:
        data = json.load(f)

    codes = []
    uris = []
    names = []
    for element in data["results"]["bindings"]:
        if element["p"]["value"] == "http://www.w3.org/ns/org#name":

            code = int(element["s"]["value"].split("/")[-1])
            uris.append(element["s"]["value"])
            codes.append(code)
            names.append(element["o"]["value"])

    df = pd.DataFrame({
        "uri": uris,
        "code": codes,
        "name": names,
    })
    return df


class EmsoMetadata:
    def __init__(self, force_update=False):

        os.makedirs(".emso", exist_ok=True)  # create a conf dir to store Markdown and other stuff
        os.makedirs(os.path.join(".emso", "jsonld"), exist_ok=True)
        os.makedirs(os.path.join(".emso", "relations"), exist_ok=True)
        ssl._create_default_https_context = ssl._create_unverified_context

        emso_metadata_file = os.path.join(".emso", "EMSO_metadata.md")
        oceansites_file = os.path.join(".emso", "OceanSites_codes.md")
        emso_sites_file = os.path.join(".emso", "EMSO_codes.md")
        sdn_vocab_p01_file = os.path.join(".emso", "jsonld", "sdn_vocab_p01.json")
        sdn_vocab_p02_file = os.path.join(".emso", "jsonld", "sdn_vocab_p02.json")
        sdn_vocab_p06_file = os.path.join(".emso", "jsonld", "sdn_vocab_p06.json")
        sdn_vocab_p07_file = os.path.join(".emso", "jsonld", "sdn_vocab_p07.json")
        sdn_vocab_l05_file = os.path.join(".emso", "jsonld", "sdn_vocab_l05.json")
        sdn_vocab_l06_file = os.path.join(".emso", "jsonld", "sdn_vocab_l06.json")
        sdn_vocab_l22_file = os.path.join(".emso", "jsonld", "sdn_vocab_l22.json")
        sdn_vocab_l35_file = os.path.join(".emso", "jsonld", "sdn_vocab_l35.json")
        edmo_codes_jsonld = os.path.join(".emso", "edmo_codes.json")
        spdx_licenses_file = os.path.join(".emso", "spdx_licenses.md")

        tasks = [
            [emso_metadata_url, emso_metadata_file, "EMSO metadata"],
            [oceansites_codes_url, oceansites_file, "OceanSites"],
            [emso_codes_url, emso_sites_file, "EMSO codes"],
            [sdn_vocab_p01, sdn_vocab_p01_file, "SDN Vocab P01"],
            [sdn_vocab_p02, sdn_vocab_p02_file, "SDN Vocab P02"],
            [sdn_vocab_p06, sdn_vocab_p06_file, "SDN Vocab P06"],
            [sdn_vocab_p07, sdn_vocab_p07_file, "SDN Vocab P07"],
            [sdn_vocab_l05, sdn_vocab_l05_file, "SDN Vocab L05"],
            [sdn_vocab_l06, sdn_vocab_l06_file, "SDN Vocab L06"],
            [sdn_vocab_l22, sdn_vocab_l22_file, "SDN Vocab L22"],
            [sdn_vocab_l35, sdn_vocab_l35_file, "SDN Vocab L35"],
            [edmo_codes, edmo_codes_jsonld, "EDMO codes"],
            [spdx_licenses_github, spdx_licenses_file, "spdx licenses"]
        ]

        download_files(tasks)

        tables = process_markdown_file(emso_metadata_file)
        self.global_attr = tables["Global Attributes"]
        self.variable_attr = tables["Variable Attributes"]
        self.dimension_attr = tables["Dimension Attributes"]
        self.qc_attr = tables["Quality Control Attributes"]

        tables = process_markdown_file(oceansites_file)
        self.oceansites_sensor_mount = list(tables["Sensor Mount"]["sensor_mount"].values)
        self.oceansites_sensor_orientation = list(tables["Sensor Orientation"]["sensor_orientation"].values)
        self.oceansites_data_modes = list(tables["Data Modes"]["Value"].values)
        self.oceansites_data_types = list(tables["Data Types"]["Data type"].values)

        tables = process_markdown_file(emso_sites_file)
        self.emso_regional_facilities = list(tables["EMSO Regional Facilities"]["EMSO Regional Facilities"].values)
        self.emso_sites = list(tables["EMSO Sites"]["EMSO Site"].values)

        rich.print("Loading spdx licenses...")
        tables = process_markdown_file(spdx_licenses_file)
        t = tables["Licenses with Short Idenifiers"]
        # remove extra '[' ']' in license identifiers
        new_ids = [value.replace("[", "").replace("]", "") for value in t["Short Identifier"]]
        self.spdx_license_names = new_ids
        self.spdx_license_uris = {lic: f"https://spdx.org/licenses/{lic}" for lic in self.spdx_license_names}

        rich.print("Loading SeaDataNet vocabularies...")
        sdn_vocabs = {
            "P01": sdn_vocab_p01_file,
            "P02": sdn_vocab_p02_file,
            "P06": sdn_vocab_p06_file,
            "P07": sdn_vocab_p07_file,
            "L05": sdn_vocab_l05_file,
            "L06": sdn_vocab_l06_file,
            "L22": sdn_vocab_l22_file,
            "L35": sdn_vocab_l35_file
        }

        self.sdn_vocabs_ids = {}
        self.sdn_vocabs_pref_label = {}
        self.sdn_vocabs_uris = {}
        self.sdn_vocabs = {}
        self.sdn_vocabs_narrower = {}
        self.sdn_vocabs_broader = {}
        self.sdn_vocabs_related = {}

        t = time.time()
        # Process raw SeaDataNet JSON-ld files and store them sliced in short JSON files
        for vocab, jsonld_file in sdn_vocabs.items():
            csv_filename = os.path.join(".emso", f"{vocab}.csv")
            frelated = os.path.join(".emso", "relations",  f"{vocab}.related")
            fnarrower = os.path.join(".emso", "relations",  f"{vocab}.narrower")
            fbroader = os.path.join (".emso", "relations",  f"{vocab}.broader")
            if os.path.exists(csv_filename):
                df = pd.read_csv(csv_filename)
                with open(frelated) as f:
                    related = json.load(f)
                with open(fnarrower) as f:
                    narrower = json.load(f)
                with open(fbroader) as f:
                    broader = json.load(f)
            else:
                rich.print(f"Loading SDN {vocab}...", end="")
                df, narrower, broader, related = self.load_sdn_vocab(jsonld_file)
                rich.print("[green]done!")
                for filename, values in {fnarrower: narrower, fbroader: broader, frelated: related}.items():
                    with open(filename, "w") as f:
                        json.dump(values, f)
            # for vocab, df in self.sdn_vocabs.items():
                # Storing to CSV to make it easier to search
                df = df[["id", "uri", "prefLabel", "definition"]]
                filename = os.path.join(".emso", f"{vocab}.csv")
                df.to_csv(filename, index=False)

            self.sdn_vocabs[vocab] = df
            self.sdn_vocabs_narrower[vocab] = narrower
            self.sdn_vocabs_broader[vocab] = broader
            self.sdn_vocabs_related[vocab] = related
            self.sdn_vocabs_pref_label[vocab] = df["prefLabel"].values
            self.sdn_vocabs_ids[vocab] = df["id"].values
            self.sdn_vocabs_uris[vocab] = df["uri"].values

        edmo_csv = os.path.join(".emso", f"edmo_codes.csv")
        if not os.path.exists(edmo_csv):
            self.edmo_codes = get_edmo_codes(edmo_codes_jsonld)
            self.edmo_codes.to_csv(edmo_csv, index=False)
        else:
            self.edmo_codes = pd.read_csv(edmo_csv)


    @staticmethod
    def clear_downloads():
        """
        Clears all files in .emso folder
        """
        files = os.listdir(".emso")
        for f in files:
            if os.path.isfile(f):
                os.remove(os.path.join(".emso", f))

    @staticmethod
    def load_sdn_vocab(filename):
        """
        Loads a SDN vocab into a pandas dataframe
        """
        with open(filename, encoding="utf-8") as f:
            contents = json.load(f)

        data = {
            "@id": [],
            "dce:identifier": [],
            "prefLabel": [],
            "definition": []
        }
        narrower = {}
        broader = {}
        related = {}
        for element in contents["@graph"]:
            uri = element["@id"]
            if element["@type"] != "skos:Concept":
                continue

            for key in data.keys():
                if type(element[key]) == dict:
                    value = element[key]["@value"]
                else:  # assuming string
                    value = element[key]
                data[key].append(value)

            # Initialize as empty list
            narrower[uri] = []
            broader[uri] = []
            related[uri] = []

            # If present, store relationships
            if "narrower" in element.keys():
                narrower[uri] = element["narrower"]
            if "broader" in element.keys():
                broader[uri] = element["broader"]
            if "related" in element.keys():
                related[uri] = element["related"]

        df = pd.DataFrame(data)
        df = df.rename(columns={"@id": "uri", "dce:identifier": "id"})
        return df, narrower, broader, related

    @staticmethod
    def harmonize_uri(uri):
        """
        Takes a SDN URI and make sure that uses http instead of https and that it finishes with a /
        """
        if uri.startswith("https"):
            uri = uri.replace("https", "http")

        if not uri.endswith("/"):
            uri += "/"
        return uri

    def vocab_get(self, vocab_id, uri, key):
        """
        Search in vocab <vocab_id> for the element with matching uri and return element identified by key
        """
        uri = self.harmonize_uri(uri)
        __allowed_keys = ["prefLabel", "id", "definition"]
        if key not in __allowed_keys:
            raise ValueError(f"Key '{key}' not valid, allowed keys: {__allowed_keys}")

        df = self.sdn_vocabs[vocab_id]
        row = df.loc[df["uri"] == uri]
        if row.empty:
            raise LookupError(f"Could not get {key} for '{uri}' in vocab {vocab_id}")
        return row[key].values[0]

    def vocab_get_by_urn(self, vocab_id, urn, key):
        """
        Search in vocab <vocab_id> for the element with matching uri and return element identified by key
        """
        __allowed_keys = ["prefLabel", "uri", "definition"]
        if key not in __allowed_keys:
            raise ValueError(f"Key '{key}' not valid, allowed keys: {__allowed_keys}")

        df = self.sdn_vocabs[vocab_id]
        row = df.loc[df["id"] == urn]
        if row.empty:
            raise LookupError(f"Could not get {key} for '{urn}' in vocab {vocab_id}")
        return row[key].values[0]

    def get_relations(self, vocab_id, uri, relation, target_vocab):
        """
        Takes a relation list from a vocabulary (narrower, broader or related), looks for a term identified by URI and
        returns a list of all the terms within that relationtship that are from the vocabuary target_vocab.

        This function is useful to get related metadata from a term, from instance

            "P01", <param>, "related", "P06" -> get the prefered units for a parameter listed within P01
            "L22", <model>, "related", "L35" -> get the  manufacturer of a sensor
            "P02", <param>, "narrower", "P01" -> get all possible fine-grained parameters values from a braod parameter

        :param vocab_id: ID of the vocabulary being used
        :param uri: URI of the term whose relations will be explored
        :param relation: type of relationship, possible values are narrower, broader and related
        :param target_vocab: id of the vocabulary terms that we want to find
        :returns: list with matches
        """
        __valid_relations = ["narrower", "broader", "related"]
        uri = self.harmonize_uri(uri)

        if relation not in __valid_relations:
            raise LookupError(f"Not a valid relation: '{relation}', expected one of '{__valid_relations} ")

        if relation == "narrower":
            relations = self.sdn_vocabs_narrower[vocab_id]
        elif relation == "broader":
            relations = self.sdn_vocabs_broader[vocab_id]
        else:  # related
            relations = self.sdn_vocabs_related[vocab_id]

        uri_relations = relations[uri]

        if type(uri_relations) == str:  # make sure it's a list
            uri_relations = [uri_relations]

        results = []
        for term in uri_relations:
            if target_vocab in term:
                results.append(term)
        return results

    def get_relation(self, vocab_id, uri, relation, target_vocab):
        """
        The same as get relations but throws an error if more than one element are found
        """
        results = self.get_relations(vocab_id, uri, relation, target_vocab)
        if len(results) != 1:
            raise LookupError(f"Expected 1 value, got {len(results)}")

        return results[0]
