#!/usr/bin/env python3
"""

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 1/3/23
"""

import rich
from rich.console import Console
from rich.table import Table
from rich.style import Style
from rich.progress import Progress
import pandas as pd
import re
from metadata import EmsoMetadata


class ErddapTester:
    def __init__(self):
        """
        This class implements the tests to ensure that the metadata in a particular ERDDAP is harmonized with the EMSO
        metadata standards. The tests are configured in the 'EMSO_metadata.md' document. There should be 2 different
        tables with the tests defined, one for the global attributes and another one for tests to be carreid
        """
        # Dict to store all erddap. KEY is the test identifier while value is the method
        rich.print("[blue]Setting up ERDDAP tests...")

        self.metadata = EmsoMetadata(True)

        self.__config_file = "EMSO_metadata.md"
        self.global_tests = []  # tests to be applied to global attributes
        self.variable_tests = []  # tests to be applied to variable attributes

        # This dict assigns a key (or test name) with a method within this class.
        # To implement a new test add a new
        self.implemented_tests = {
            "data_type": self.__test_data_type,
            "coordinate": self.__test_coordinate,
            "depth": self.__test_depth,
            "edmo_code": self.__test_edmo_code,
            "emso_site_code": self.__test_emso_site_code,
            "emso_facility": self.__test_emso_site_code,
            "email": self.__test_email,
            "cf_standard_name": self.__test_cf_standard_name,
            "sdn_vocab_urn": self.__test_sdn_vocab_urn,
            "oceansites_sensor_mount": self.__test_oceansites_sensor_mount,
            "oceansites_sensor_orientation": self.__test_oceansites_sensor_orientation,
        }

    def print_results(self, df):
        """
        Prints the results in a nice-looking table using rich
        :param df: DataFrame with test results
        """
        table = Table(title="ERDDAP test report")
        table.add_column("variable", justify="right", no_wrap=True, style="cyan")
        table.add_column("attribute", justify="right")
        table.add_column("required", justify="right")
        table.add_column("passed", justify="right")
        table.add_column("message", justify="right")
        table.add_column("value", justify="left")
        section = "global"
        for _, row in df.iterrows():
            # Process styles depending on the passed and required fields
            style = ""
            if row["message"] == "unimplemented":
                style = Style(color="bright_black", bold=False)
            elif row["required"] and not row["passed"]:
                style = Style(color="red", bold=True)
            elif row["passed"]:
                style = Style(color="green", bold=True)
            elif not row["required"] and not row["passed"]:
                style = Style(color="yellow", bold=False)

            if row["variable"] != section:  # add a new empty row with end section
                section = row["variable"]
                table.add_row(style=style, end_section=True)

            table.add_row(row["variable"], row["attribute"], str(row["required"]), str(row["passed"]), row["message"],
                          row["value"], style=style)

        console = Console()
        console.print(table)

        total_tests = len(df)
        total_passed = len(df[df["passed"] == True])
        rich.print(f"Total tests passed: {total_passed} of {total_tests}")

        r = df[df["required"] == True]  # required test
        req_tests = len(r)
        req_passed = len(r[r["passed"] == True])
        rich.print(f"Required tests passed: {req_tests} of {req_passed}")

        o = df[df["required"] == False]  # required test
        opt_tests = len(o)
        opt_passed = len(o[o["passed"] == True])
        rich.print(f"Required tests passed: {opt_passed} of {opt_tests}")

        def generate_bar_col(n):
            if n > 0.95:
                return "green"
            if n > 0.8:
                return "blue"
            if n > 0.6:
                return "yellow"
            if n > 0.4:
                return "dark_orange"
            return "red"

        t_color = generate_bar_col(total_passed / total_tests)
        r_color = generate_bar_col(req_passed / req_tests)
        o_color = generate_bar_col(opt_passed / opt_tests)

        with Progress(auto_refresh=False) as progress:
            req_task = progress.add_task(f"[{t_color}]Required tests...", total=req_tests)
            opt_task = progress.add_task(f"[{r_color}]Optional tests...", total=opt_tests)
            total_task = progress.add_task(f"[{o_color}]Total tests...", total=total_tests)

            progress.update(req_task, advance=req_passed)
            progress.update(opt_task, advance=opt_passed)
            progress.update(total_task, advance=total_passed)
            progress.stop()

    def run_test(self, test_name, args, attribute: str, metadata, required, varname, results) -> (bool, str, any):
        """
        Applies the method test to the dict data and stores the output into results
        :param test_name: Name of the test tp apply
        :param args: arguments to be passed to test_method
        :param attribute: name of the attribute to be tested
        :param metadata: dict with the metadata being tested
        :param required: flag indicating if test is mandatory
        :param varname: variable name for the applied test (global for generic dataset metadata)
        :param results: dict with arrays to store the results of the tests
        :return: a tuple with (bool, str, any). Boolean indicates success, str is an error message and any is the value
                 of the attribute or None if not present.
        """
        if attribute not in metadata.keys():
            passed = False
            message = "not found"
            value = ""
        else:
            if test_name not in self.implemented_tests.keys():
                rich.print(f"[red]Test '{test_name}' not implemented!")
                raise LookupError(f"Test {test_name} not found")

            value = metadata[attribute]
            test_method = self.implemented_tests[test_name]
            passed, message = test_method(value, args) # apply test method

        results["attribute"].append(attribute)
        results["variable"].append(varname)
        results["passed"].append(passed)
        results["required"].append(required)
        results["message"].append(message)
        results["value"].append(value)

        return passed, message, value

    def validate_dataset(self, metadata):
        """
        Takes the well-formatted JSON metadata from an ERDDAP dataset and processes it
        :param metadata: well-formatted JSON metadta for an ERDDAP dataset
        :return: a DataFrame with the following columns: [attribute, variable, required, passed, message, value]
        """
        rich.print(f"#### Validating dataset {metadata['global']['title']} ####")
        results = {
            "attribute": [],
            "variable": [],
            "required": [],
            "passed": [],
            "message": [],
            "value": []
        }

        # Run Global Attributes test
        for _, row in self.metadata.global_attr.iterrows():
            attribute = row["Global Attributes"]
            test_name = row["Compliance test"]
            required = row["Required"]

            if not test_name:
                rich.print(f"[yellow]WARNING: test for {attribute} not implemented!")
                continue

            args = []
            if "#" in test_name:
                test_name, args = test_name.split("#")
                args = args.split(",")  # comma-separated fields are args

            self.run_test(test_name, args, attribute, metadata["global"], required, "global", results)

        # Variable tests
        for varname, var_metadata in metadata["variables"].items():
            for _, row in self.metadata.variable_attr.iterrows():
                attribute = row["Variable Attributes"]
                test_name = row["Compliance test"]
                required = row["Required"]

                if not test_name:
                    rich.print(f"[yellow]WARNING: test for {attribute} not implemented!")
                    continue

                args = []
                if "#" in test_name:
                    test_name, args = test_name.split("#")
                    args = args.split(",")  # comma-separated fields are args
                self.run_test(test_name, args, attribute, metadata["variables"][varname], required, varname, results)

        df = pd.DataFrame(results)
        self.print_results(df)
        return df

    # ---------------------- TEST METHODS ------------------------ #
    # Test methods implement checks to be applied to a group metadata attributes, such as coordinates or valid email.
    # All tests should return a tuple (bool, str) tuple. The bool indicates success (true/false), while the message str
    # indicates in plain text the reason why the test failed. If the test successfully passes sucess, the return str
    # should be empty.
    # ------------------------------------------------------- #
    def __test_data_type(self, value, args) -> (bool, str):
        """
        Check if value is of the exepcted type.
        :param value: value to be tested
        :param args: list with one value containing a string of the type, like ['string'] or ['float']
        :returns: passed, error message
        """
        if len(args) != 1:
            raise ValueError("Expected exacly one extra argument with type")
        data_type = args[0]

        if data_type in ["str", "string"]:
            # check string
            if type(value) != str:
                return False, "not a string"

        elif data_type in ["int", "integer", "unsigned"]:
            # check string
            if type(value) != int:
                return False, "not an integer"

        elif data_type in ["float", "double"]:
            # check string
            if type(value) != float:
                return False, "not a float"

        elif data_type in ["date"]:
            return False, "unimplemented"

        elif data_type in ["datetime"]:
            try:
                pd.Timestamp(value)
            except ValueError:
                return False, "Datetime not valid, expecting format 'YYY-dd-mmTHH:MM:SS+tz'"
        else:
            raise ValueError(f"Unrecodgnized data type '{data_type}'...")

        return True, ""

    def __test_date(self, value, args) -> (bool, str):
        return False, "unimplemented"

    def __test_datetime(self, value, args):
        return False, "unimplemented"

    # -------- coordinates -------- #
    def __test_depth(self, value, args) -> (bool, str):
        # from mariana trench bottom (11km) to 1000 m above sea (enough for marine data)
        __depth_limits = [-1000, 11000]
        try:
            value = float(value)
        except ValueError:
            return False, f"Could not convert '{value}' to float"
        if value < __depth_limits[0] or value > __depth_limits[1]:
            return False, f"Valid depth range {__depth_limits}"
        return True, ""

    def __test_coordinate(self, value, args) -> (bool, str):
        try:
            value = float(value)
        except ValueError:
            return False, f"Could not convert '{value}' to float"
        if value < -90 or value > 90:
            return False, "coordiante should be between -90 and +90"
        return True, ""

    # -------- Common formats -------- #
    def __test_email(self, value, args) -> (bool, str):
        if len(value) > 7:
            if not re.match("[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+", value):
                return True, ""
            return False, f"email '{value} not valid"

    def __test_edmo_code(self, value, args):
        if type(value) == str:
            rich.print("[yellow]WARNING: EDMO code should be integer! converting from string to int")
            value = int(value)
        if value in self.metadata.edmo_codes:
            return True, ""
        return False, f"'{value}' is not a valid EDMO code"

    def __test_sdn_vocab_urn(self, value, args):
        """
        Tests that the value is a valid URN for a specific SeaDataNet Vocabulary. the vocab should be specified in *args
        """
        if len(args) != 1:
            raise SyntaxError("Vocabulary identifier should be passed in args, e.g. 'P01'")
        vocab = args[0]

        if vocab not in self.metadata.sdn_vocabs.keys():
            raise ValueError(f"Vocabulary '{vocab}' not loaded! Loaded vocabs are {self.metadata.sdn_vocabs.keys()}")

        if value in self.metadata.sdn_vocabs[vocab]:
            return True, ""

        return False, f"Not a valid '{vocab}' URN"

    def __test_emso_site_code(self, value, args):
        __valid_codes = ["Azores", "Black Sea", "Canary Islands", "Cretan Sea", "Hellenic Arc", "Iberian Margin",
                         "Ligurian Sea", "Molène", "OBSEA", "SmartBay", "South Adriatic Sea", "Western Ionian",
                         "Western Mediterranean Sea"]
        if value not in __valid_codes:
            return False, "EMSO site code not valid"

        return True, ""

    def __test_cf_standard_name(self, value, args):
        """
        Checks if value is in Climate and Forescast standard names
        """
        if value in self.metadata.standard_names:
            return True, ""

        return False, "Not a valid CF Standard Name"

    def __test_oceansites_sensor_mount(self, value, args):
        """
        Checks if value is in OceanSites sensor mount table
        """
        return False, "unimplemented"

    def __test_oceansites_sensor_orientation(self, value, args):
        """
        Checks if value is in Climate and Forescast standard names
        """
        return False, "unimplemented"

