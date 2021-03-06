
import random
import struct
import subprocess
import nmap

from time import sleep
from collections import defaultdict

from components.framework.Debug import Debug
# from components.helpers.BlinktSupport import BlinktSupport
from components.helpers.Format import Format
from components.helpers.IpValidator import *
from components.helpers.ModuleManager import ModuleManager
from components.modules.Enumerate.Result2Html import Result2Html
from components.modules.Enumerate.TargetInfo import TargetInfo


# -.-. --- .-. . -.-- .... .- ... -. --- --. --- --- -.. .. -.. . .- ...


class Enumerate:
    def __init__(self, path, debug):
        self.enumerate = Debug(name="Enumerate", type="Module", debug=debug)
        self._debug = debug

        # Setup module manager
        self.module_manager = ModuleManager(debug=debug, save_needs_confirm=True)

        # import config data for this module
        self.current_config = self.module_manager.get_module_by_name(self.enumerate._name)
        if not self.current_config:
            self.enumerate.debug("Error: could not import config of " + self.enumerate._name, color=Format.color_danger)

        # Import default system path
        self.path = path

        # Import interface else use default
        self.interface = self.current_config.options["interface"]\
            if self.current_config.options["interface"] == "wlan0"\
            or self.current_config.options["interface"] == "usb0"\
            else "wlan0"

        self.enumerate.debug("Using interface: " + self.interface)

        # ~Produce list of usable ip addresses~
        self.raw_ip_targets = self.current_config.options["ip_targets"]
        self.raw_ip_exclusions = self.current_config.options["ip_exclusions"]
        self.ip_list = [ip for ip in self.get_ip_list(self.raw_ip_targets)
                        if ip not in self.get_ip_list(self.raw_ip_exclusions)]

        # have to do it this way to avoid actions happening to both lists
        self.ip_list_shuffled = [ip for ip in self.ip_list]
        random.shuffle(self.ip_list_shuffled)

        # ~Produce list of usable ports~
        self.raw_ports = self.current_config.options["port_targets"]
        self.raw_port_exclusions = self.current_config.options["port_exclusions"]
        self.port_list = [port for port in self.get_port_list(self.raw_ports)
                          if port not in self.get_port_list(self.raw_port_exclusions)]

        # ~Produce list of usable users.txt~
        self.user_list = []
        with open(self.path + "/modules/Enumerate/users.txt") as user_file:
            for line in user_file:
                try:
                    user, _, password = line.strip().partition(":")
                    self.user_list.append([user, password])
                except Exception as user_list_err:
                    self.enumerate.debug("Error parsing users: %s" % user_list_err, color=Format.color_warning)

        # ~Produce list of default passwords~
        self.default_passwords = []
        with open(self.path + "/modules/Enumerate/default_passwords.txt") as password_file:
            for line in password_file:
                self.default_passwords.append(line)

        self.rpc_timeout = float(self.current_config.options['rpc_timeout_start'])
        self.rpc_max_timeout = float(self.current_config.options['rpc_timeout_max'])
        self.rpc_timeout_increment = float(self.current_config.options['rpc_timeout_increment'])

        self.quiet = self.current_config.options["quiet"]
        self.verbose = self.current_config.options["verbose"]
        self.use_port_range = self.current_config.options["use_port_range"]

        ###############################################################################
        # The following  mappings for nmblookup (nbtstat) status codes to human readable
        # format is taken from nbtscan 1.5.1 "statusq.c".  This file in turn
        # was derived from the Samba package which contains the following
        # license:
        #    Unix SMB/Netbios implementation
        #    Version 1.9
        #    Main SMB server routine
        #    Copyright (C) Andrew Tridgell 1992-1999
        #
        #    This program is free software; you can redistribute it and/or modif
        #    it under the terms of the GNU General Public License as published b
        #    the Free Software Foundation; either version 2 of the License, o
        #    (at your option) any later version
        #
        #    This program is distributed in the hope that it will be useful
        #    but WITHOUT ANY WARRANTY; without even the implied warranty o
        #    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See th
        #    GNU General Public License for more details
        #
        #    You should have received a copy of the GNU General Public Licens
        #    along with this program; if not, write to the Free Softwar
        #    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA

        self.nbt_info = [
            ["__MSBROWSE__", "01", 0, "Master Browser"],
            ["INet~Services", "1C", 0, "IIS"],
            ["IS~", "00", 1, "IIS"],
            ["", "00", 1, "Workstation Service"],
            ["", "01", 1, "Messenger Service"],
            ["", "03", 1, "Messenger Service"],
            ["", "06", 1, "RAS Server Service"],
            ["", "1F", 1, "NetDDE Service"],
            ["", "20", 1, "File Server Service"],
            ["", "21", 1, "RAS Client Service"],
            ["", "22", 1, "Microsoft Exchange Interchange(MSMail Connector)"],
            ["", "23", 1, "Microsoft Exchange Store"],
            ["", "24", 1, "Microsoft Exchange Directory"],
            ["", "30", 1, "Modem Sharing Server Service"],
            ["", "31", 1, "Modem Sharing Client Service"],
            ["", "43", 1, "SMS Clients Remote Control"],
            ["", "44", 1, "SMS Administrators Remote Control Tool"],
            ["", "45", 1, "SMS Clients Remote Chat"],
            ["", "46", 1, "SMS Clients Remote Transfer"],
            ["", "4C", 1, "DEC Pathworks TCPIP service on Windows NT"],
            ["", "52", 1, "DEC Pathworks TCPIP service on Windows NT"],
            ["", "87", 1, "Microsoft Exchange MTA"],
            ["", "6A", 1, "Microsoft Exchange IMC"],
            ["", "BE", 1, "Network Monitor Agent"],
            ["", "BF", 1, "Network Monitor Application"],
            ["", "03", 1, "Messenger Service"],
            ["", "00", 0, "Domain/Workgroup Name"],
            ["", "1B", 1, "Domain Master Browser"],
            ["", "1C", 0, "Domain Controllers"],
            ["", "1D", 1, "Master Browser"],
            ["", "1E", 0, "Browser Service Elections"],
            ["", "2B", 1, "Lotus Notes Server Service"],
            ["IRISMULTICAST", "2F", 0, "Lotus Notes"],
            ["IRISNAMESERVER", "33", 0, "Lotus Notes"],
            ['Forte_$ND800ZA', "20", 1, "DCA IrmaLan Gateway Server Service"]
        ]
        # ~end of enum4linux.pl-derived code~

    def run(self):
        # ~Runs all the things~
        # ---------------------

        target_ips = defaultdict(TargetInfo)  # Init of dictionary

        current_ip_in_list = 1
        ips_in_list = len(self.ip_list_shuffled)

        for ip in self.ip_list_shuffled:  # Make it less obvious
            self.enumerate.debug("Target (%s) %s of %s" % (ip, current_ip_in_list, ips_in_list))

            current = TargetInfo()

            self.enumerate.debug("Starting ICMP", color=Format.color_info)
            # check current IP responds to ICMP
            current.RESPONDS_ICMP = self.check_target_is_alive(ip, interface=self.interface)
            self.enumerate.debug("%s responds to ICMP? %s" % (ip, current.RESPONDS_ICMP))

            self.enumerate.debug("Starting ARP", color=Format.color_info)
            # check current IP responds to ARP
            arp_response = self.get_targets_via_arp(ip, interface=self.interface)

            if arp_response:
                try:
                    current.RESPONDS_ARP = True
                    current.MAC_ADDRESS = arp_response[0][1]
                    current.ADAPTER_NAME = arp_response[0][2]
                    self.enumerate.debug("%s responds to ARP? %s" % (ip, current.RESPONDS_ARP))
                    self.enumerate.debug("%s's physical address is %s" % (ip, current.MAC_ADDRESS))
                    self.enumerate.debug("%s's adapter name is %s" % (ip, current.ADAPTER_NAME))
                except Exception as Err:
                    self.enumerate.debug("ARP Err: %s" % Err, color=Format.color_warning)
            else:
                self.enumerate.debug("No ARP response from %s" % ip)

            # check route to this target
            if self.interface != "usb0":
                self.enumerate.debug("Starting Route", color=Format.color_info)
                current.ROUTE = self.get_route_to_target(ip, map_host_names=False, interface=self.interface)

            # NBT STAT
            self.enumerate.debug("Starting NBTSTAT", color=Format.color_info)
            current.NBT_STAT = self.get_nbt_stat(ip)

            # RPC CLIENT
            self.enumerate.debug("Starting RPCCLIENT", color=Format.color_info)
            current.DOMAIN_GROUPS, current.DOMAIN_USERS, current.PASSWD_POLICY = self.get_rpcclient(user_list=self.user_list, password_list=self.default_passwords, target=ip)
            # current.DOMAIN

            # NMAP to determine OS, port and service info
            self.enumerate.debug("Starting NMAP", color=Format.color_info)
            nmap_output = self.nmap(ip)  # TODO portsCSV
            if len(nmap_output) == 2:
                self.enumerate.debug("NMAP parsing output")
                current.PORTS += nmap_output[1]
                current.OS_INFO += nmap_output[0]
            else:
                self.enumerate.debug("Error: NMAP output did not match expectations", color=Format.color_warning)
                current.PORTS = False
                current.OS_INFO = False  # making it easier to parse

            # SMBCLIENT / SHARE INFO
            self.enumerate.debug("Starting SMBCLIENT", color=Format.color_info)
            current.SHARE_INFO = self.get_share(ip)


            # SAVE RESULTS
            self.enumerate.debug("Saving results from %s" % ip, color=Format.color_success)
            # Add target information to dict
            target_ips[ip] = current
            current_ip_in_list += 1

        # Write output to html
        with open(self.path + "/modules/Enumerate/output.html", "w") as out:
            self.enumerate.debug("Writing all results to output.html", color=Format.color_info)
            html = Result2Html(debug=self._debug)
            output = html.result2html(target_ips, self.ip_list)
            out.write(output)

        return  # End of run

    def get_port_list(self, raw_ports):
        """
        :param raw_ports:
        :return list string?:
        :return none:
        """
        # TODO 01/03/18 [1/2] Add error handling
        # Comma separated list of Ports
        if "," in raw_ports:
            return raw_ports.strip().split(',')
        # Range of ports
        elif "-" in raw_ports:
            start, _, end = raw_ports.strip().partition('-')
            return [port for port in range(int(start), int(end))]
        # Single port
        elif 0 <= int(raw_ports) <= 65535:
            return [raw_ports]

        # Else Bad entry
        self.enumerate.debug(
            "Error: Invalid type, must be lower_port-upper_port, single port or p1, p2, p3, etc...")
        return None

    def get_ip_list(self, raw_ips):
        """
        :param raw_ips:
        :return list string:
        :return none:
        """
        # TODO 01/03/18 [2/2] Add error handling
        # Comma separated list of IPs
        if "," in raw_ips:
            return raw_ips.strip().split(',')
        # Range of IPs
        elif "-" in raw_ips:
            start, _, end = raw_ips.strip().partition('-')

            # If you are looking at this line wondering wtf give this a go: socket.inet_ntoa(struct.pack('>I', 5))
            return [socket.inet_ntoa(struct.pack('>I', i)) for i in
                    range(struct.unpack('>I', socket.inet_aton(start))[0],
                          struct.unpack('>I', socket.inet_aton(end))[0])]
        # Single IP
        elif IpValidator.is_valid_ipv4_address(raw_ips):
            return [raw_ips]
        # Bad entry
        else:
            self.enumerate.debug("Error: Invalid type, must be lower_ip-upper_ip or ip1, ip2, ip3, etc...")
            return None

    def get_share(self, target):
        """
        :param target:
        :return list of 3 lists first contains share name second share type and third share description:
        """
        def parse_this_share(shares):
            shares = shares.splitlines()  # Spilt output into list

            output = [[], [], []]  # Create list to hold output

            # Delete first line (results in shares being empty if it failed)
            del shares[0]

            # If content still exists in shares (it completed successfully)
            if shares:

                # Clean up formatting (Needs to be like this)
                del shares[0]
                del shares[0]

                regex = re.compile("^\s+([^\s]*)\s*([^\s]*)\s*([^\n]*)", flags=re.M)  # Compile regex
                for line in shares:  # For each share
                    result = re.search(regex, line)  # Search for a match to regex
                    if result:  # If found
                        result = [res if not None else "" for res in result.groups()]  # Ensure valid
                        for index in range(0, 3):
                            output[index].append(result[index])  # Load result into the output list

            self.enumerate.debug("get_share: output generated successfully", color=Format.color_success)
            return output

        for user, passwd in self.user_list:
            if passwd:
                try:
                    shares = subprocess.run("smbclient " + "-L " + target + " -U " + user + "%" + passwd, shell=True,
                                            stdout=subprocess.PIPE).stdout.decode('utf-8')
                except Exception as e:
                    if "non-zero" in e:
                        if "NT_STATUS_CONNECTION_REFUSED" in shares:
                            self.enumerate.debug("get_share: Error NT_STATUS_CONNECTION_REFUSED")
                            continue

                        # 99% of the time, errors here are subprocess calls returning non-zero
                    else:
                        self.enumerate.debug("get_share: Critical Error %s" % e, color=Format.color_danger)
                        return False
                else:
                    if "NT_STATUS_CONNECTION_REFUSED" in shares or "NT_STATUS_LOGON_FAILURE" in shares:
                        continue

                    return parse_this_share(shares)

            else:
                for password in self.default_passwords:
                    try:
                        shares = subprocess.run("smbclient " + "-L " + target + " -U " + user + "%" + passwd,
                                                shell=True,
                                                stdout=subprocess.PIPE).stdout.decode('utf-8')
                    except Exception as e:
                        if "non-zero" in e:
                            if "NT_STATUS_CONNECTION_REFUSED" in shares:
                                self.enumerate.debug("get_share: Error NT_STATUS_CONNECTION_REFUSED ")
                                continue

                            # 99% of the time, errors here are subprocess calls returning non-zero
                        else:
                            self.enumerate.debug("get_share: Critical Error %s" % e, color=Format.color_danger)
                            return False
                    else:
                        if "NT_STATUS_CONNECTION_REFUSED" in shares or "NT_STATUS_LOGON_FAILURE" in shares:
                            continue

                        return parse_this_share(shares)

    def get_groups(self, target, user, password):
        '''
        :param target:
        :param user:
        :param password:
        :return: List of samba groups on target
        '''

        # Get all groups
        groups = subprocess.run("net rpc group LIST global -I " + target + " -U  " + user + "%" + password, shell=True,
                                stdout=subprocess.PIPE).stdout.decode('utf-8')

        self.enumerate.debug(groups)

        if not (re.search("Could not connect|Connection failed:", groups, flags=re.M)):  # If successful
            groups = groups.splitlines()  # Split results into list
            return groups
        else:
            return False  # Something went wrong

    def get_users(self, target, group, user, password):
        '''
        :param target:
        :param group:
        :param user:
        :param password:
        :return: List of users in a given samba group
        '''

        # Get all users in a given group
        users = subprocess.run("net rpc group members \"" + group + "\" -I " + target + " -U " + user + "%" + password, shell=True,
                                stdout=subprocess.PIPE).stdout.decode('utf-8')

        self.enumerate.debug(users)

        if not (re.search("Could not connect|Connection failed:", users, flags=re.M)):  # If successful
            groups = users.splitlines()  # Split results into list
            return users
        else:
            return False  # Something went wrong

    def get_all_users(self, target, user, password):
        '''
        :param target:
        :param user:
        :param password:
        :return: List of lists first contains a string group name, second contains list of string user
        '''

        output = [[], [[]]]  # Make output list

        groups = self.get_groups(target, user, password)  # Get groups

        if groups:  # If groups ran successfully
            for group in groups:  # For each group
                users = self.get_users(target, group, user, password)  # Attempt to harvest users
                if users:  # If successful
                    output[0].append(group)  # Load group into output
                    output[1].append(users)  # Load user list into output

        if output:  # If output was generated
            return output
        else:
            return False  # Something went wrong

    # NMAP scans for service and operating system detection
    def nmap(self, target_ip):

        """
        :return list of list of list of strings:
        :return none:
        """
        self.enumerate.debug("Nmap initializing...", color=Format.color_secondary)
        nm = nmap.PortScanner()  # Declare python NMAP object
        output_list = []  # List for saving the output of the commands to

        def service_parsing():  # local function for parsing service and port info

            parsed_output = []

            for protocol in nm[target_ip].all_protocols():

                for port in nm[target_ip][protocol]:
                    nmap_results = nm[target_ip][protocol][port]
                    parsed_output.append(
                        [str(port), nmap_results['product'] if nmap_results['product'] else "null",
                         nmap_results['version'] if nmap_results['version'] else "null",
                         nmap_results['state'] if nmap_results['state'] else "null"])

            output_list.append(parsed_output)  # Add parsed data to the output list

            return

        def os_parsing(output):  # Local function for parsing OS information
            # (required as python NMAP OS isn't working correctly)

            parsed_output = []
            # Separating OS info and appending it to the output list
            for line in output.splitlines():
                if "OS" in line and "detection" not in line and "matches" not in line:

                    if "Running:" in line:
                        new_line = line.strip('Running:').split(',')
                        parsed_output.append(new_line)

                    elif "Aggressive OS guesses" in line:
                        new_line = line.strip('Aggressive OS guesses:').split(', ')
                        parsed_output.append(new_line)

                    elif "OS details" in line:
                        new_line = line.strip('OS details:')
                        parsed_output.append(new_line)

            output_list.append(parsed_output)

            return
        try:
            if self.quiet == "true":  # If quiet scan flag is set use "quiet" scan pre-sets
                self.enumerate.debug("NMAP: quiet mode", color=Format.format_clear)
                command = "-sV --version-light"

                if self.use_port_range == "true":  # If a port range has been specified use
                    nm.scan(hosts=target_ip, ports=self.raw_ports, arguments=command)
                else:
                    nm.scan(hosts=target_ip, arguments=command)

                # Run "quiet" nmap OS scan and save output to a variable for parsing
                os_output = subprocess.run(["nmap", "-O", target_ip], shell=True,
                                           stdout=subprocess.PIPE).stdout.decode('utf-8')

            else:  # Use "loud" scan pre-sets
                self.enumerate.debug("NMAP: loud mode", color=Format.format_clear)
                command = "-sV --version-all -T4"

                if self.use_port_range == "true":
                    nm.scan(hosts=target_ip, ports=self.raw_ports, arguments=command)
                else:
                    nm.scan(hosts=target_ip, arguments=command)

                # Run "loud" nmap OS scan and save output to a variable for parsing
                os_output = subprocess.run(["sudo", "nmap", "-O", "--osscan-guess", "-T5", target_ip],
                                           stdout=subprocess.PIPE).stdout.decode('utf-8')

            self.enumerate.debug("NMAP: OS parsing", color=Format.color_info)
            os_parsing(os_output)  # Call local function for nmap OS parsing
            self.enumerate.debug("NMAP: Service parsing", color=Format.color_info)
            service_parsing()  # Call local function for nmap service/port parsing
        except Exception as another_nmap_error:
            self.enumerate.debug("NMAP Error: %s" % another_nmap_error, color=Format.color_warning)
            return False

        self.enumerate.debug("NMAP: Output generated successfully", color=Format.color_success)
        return output_list  # return the output of scans in the form of a list

    def get_nbt_stat(self, target):
        """
        :return list string:
        """
        raw_nbt = subprocess.run(["sudo", "nmblookup", "-A", target],
                                 stdout=subprocess.PIPE).stdout.decode('utf-8').split('\n')
        # Basically does the same as the real NBTSTAT but really really disgusting output
        if not raw_nbt:
            self.enumerate.debug("get_nbt_stat Error: nmblookup failed", color=Format.color_warning)
            return False

        # Fixing that output
        output = []
        for line in raw_nbt:
            # Get actual results
            try:
                result = re.search("\s+(\S+)\s+<(..)>\s+-\s+?(<GROUP>)?\s+?[A-Z]\s+?(<ACTIVE>)?", line)
                if result:  # If any matches the regex

                    # Need to replace None type with ""
                    result = [res if res is not None else "" for res in result.groups()]

                    for nbt_line in self.nbt_info:
                        service, hex_code, group, descriptor = nbt_line
                        # if we need to check service or not (this is empty for some fields)
                        if service:
                            if service == result[0] and hex_code == result[1] and bool(group) == bool(result[2]):
                                self.enumerate.debug("service match: %s/%s " % (line, descriptor))
                                output.append("%s %s" % (line, descriptor))
                                break
                        else:
                            if hex_code == result[1] and bool(group) == bool(result[2]):
                                self.enumerate.debug("hex_code match: %s/%s " % (line, descriptor))
                                output.append("%s %s" % (line, descriptor))
                                break

                else:  # If it didn't match the regex
                    # Ignore the "Looking up status of [target]" line
                    if "up status of" in line or "MAC Address" in line:
                        continue

                    # No results found for target
                    elif "No reply from" in line:
                        return False

                    # still no results and line isn't empty
                    if "".join(line.split()) != "":
                        self.enumerate.debug("get_nbt_stat: No match found for %s" % line, color=Format.color_info)
                        output.append("%s" % line)

            except Exception as what_went_wrong:
                self.enumerate.debug("Something went wrong %s" % what_went_wrong, color=Format.color_warning)

        self.enumerate.debug("get_nbt_stat: Output generated successfully", color=Format.color_success)
        return output

    def rpc_request(self, user, password, target):
        if self.rpc_timeout < self.rpc_max_timeout:
            if self.rpc_timeout > 0:
                sleep(self.rpc_timeout)

            try:

                command = ["rpcclient", "-U", user, target, "-c", "getdompwinfo"]

                self.enumerate.debug("RPC Request Username - %s" % user)
                self.enumerate.debug("RPC Request Password - %s" % password)

                dompwpolicy_test_query = subprocess.run(command, input=password + "\n",
                                                        encoding="ascii", stdout=subprocess.PIPE)

                if dompwpolicy_test_query.check_returncode() is not None:
                    if "NT_STATUS_CONNECTION_REFUSED" in dompwpolicy_test_query.stdout:
                        # Unable to connect
                        self.enumerate.debug("Error: get_rpcclient: Connection refused under - %s" % user,
                                             Format.color_warning)

                        self.rpc_timeout += self.rpc_timeout_increment

                    return

                else:
                    command.pop()

                    curr_domain_info = self.extract_info_rpc(
                        subprocess.run(command + ["enumdomgroups"], input=password + "\n",
                                       encoding="ascii", stdout=subprocess.PIPE).stdout)


                    self.enumerate.debug("First few items - %s " %
                                         curr_domain_info[0])
                    curr_user_info = self.extract_info_rpc(
                        subprocess.run(command + ["enumdomusers"], input=password + "\n",
                                       encoding="ascii", stdout=subprocess.PIPE).stdout,
                        startrows=0, initchars=6)

                    self.enumerate.debug("First few characters of users - %s" %
                                         curr_user_info[0])

                    curr_password_info = self.get_password_policy(dompwpolicy_test_query.stdout)

                return [curr_domain_info, curr_user_info, curr_password_info]

            except Exception:
                return

    def get_rpcclient(self, user_list, password_list, target):
        """
        Using RPC Client command to enumerate users, password policy and groups

        :param user_list:
        :param password_list:
        :param target:
        :return none:
        """

        domain_info = []
        user_info = []
        password_info = []

        for user, passwd in user_list:
            if passwd:
                try:
                    current = self.rpc_request(user, passwd, target)

                except Exception as e:
                    if "non-zero" in e:
                        continue  # 99% of the time, errors here are subprocess calls returning non-zero
                    else:
                        self.enumerate.debug("get_rpcclient: Error %s" % e, color=Format.color_danger)

                # There must be a better way to do this I cant think of without utilising self
                # If output from rpc_request
                if current:
                    # current = [curr_domain_info, curr_user_info, curr_password_info]


                    # There may be a quicker way to do this but it would likely require another structure
                    for line in current[0]:
                        if line not in domain_info:
                            domain_info += line

                    for line in current[1]:
                        if line not in user_info:
                            user_info += line

                    if not password_info:
                        password_info = current[2]
                        
            else:
                for password in password_list:
                    try:
                        current = self.rpc_request(user, password, target)
                    except IOError as e:

                        self.enumerate.debug("Error: get_rpcrequest: %s" % e, Format.color_danger)

                        # If output from rpc_request
                        continue

                    if current:
                        # current = [curr_domain_info, curr_user_info, curr_password_info]

                        for line in current[0]:
                            if line not in domain_info:
                                domain_info += line

                        for line in current[1]:
                            if line not in user_info:
                                user_info += line

                        if not password_info:
                            password_info = current[2]

                        break

        return domain_info, user_info, password_info

    def get_password_policy(self, raw_command):
        """
        :param raw_command:
        :return int, bool, bool, bool, bool, bool, bool:
        """
        length = 0
        clear_text_pw = False
        refuse_pw_change = False
        lockout_admins = False
        complex_pw = False
        pw_no_anon_change = False
        pw_no_change = False

        if "min_password_length" in raw_command:
            for s in raw_command.split():
                if s.isdigit():
                    length = s
                    self.enumerate.debug("Min Password Length: " + s, Format.color_info)

        if "DOMAIN_PASSWORD_STORE_CLEARTEXT" in raw_command:
            clear_text_pw = True
            self.enumerate.debug("Password Store Cleartext Flag", Format.color_info)
        if "DOMAIN_REFUSE_PASSWORD_CHANGE" in raw_command:
            refuse_pw_change = True
            self.enumerate.debug("Refuse Password Change Flag", Format.color_info)
        if "DOMAIN_PASSWORD_LOCKOUT_ADMINS" in raw_command:
            lockout_admins = True
            self.enumerate.debug("Password Lockout Admins Flag", Format.color_info)
        if "DOMAIN_PASSWORD_COMPLEX" in raw_command:
            complex_pw = True
            self.enumerate.debug("Password Complex Flag", Format.color_info)
        if "DOMAIN_PASSWORD_NO_ANON_CHANGE" in raw_command:
            pw_no_anon_change = True
            self.enumerate.debug("Password No Anon Change Flag", Format.color_info)
        if "DOMAIN_PASSWORD_NO_CLEAR_CHANGE" in raw_command:
            pw_no_change = True
            self.enumerate.debug("Password No Clear Change Flag", Format.color_info)

        output = [length, clear_text_pw, refuse_pw_change, lockout_admins, complex_pw, pw_no_anon_change, pw_no_change]
        self.enumerate.debug("get_password_policy: Output generated successfully", color=Format.color_success)

        return output

    def extract_info_rpc(self, rpc_out, startrows=1, initchars=7):
        """

        :param rpc_out:
        :param startrows:
        :param initchars:

        :return: Returns a list of lists containing user/group followed by rid as a pair
                 e.g.[[user/group, rid]]
        """

        rpc_out = rpc_out.split("\n")

        if startrows > 0:
            del rpc_out[0:startrows]
        else:
            del rpc_out[0]

        del rpc_out[-1]

        output = []

        for line in rpc_out:
            # output will look like [[user/group, rid], [user/group, rid]]
            output += [[line[initchars:-1].split('] rid:[')]]

        # self.enumerate.debug("extract_info_rpc: Output generated successfully", color=Format.color_success)
        return output

    def check_target_is_alive(self, target, interface="wlan0", ping_count=0, all_ips_from_dns=False, get_dns_name=False,
                              contain_random_data=True, randomise_targets=False, source_address="self", verbose=False):
        """
        Uses ICMP pings to check that hosts are online/responsive. This makes use of the FPing command line tool so is
        able to ping multiple hosts

        :param target: Either target via IPv4, IPv4 range, list of IPv4's, DNS Name(s?!)
        :param interface: Choose which interface the pings go from. Defaults to USB0
        :param ping_count: Will ping as many times as the input asks for
        :param all_ips_from_dns: Scans all IP address's relating to that DNS _name
        :param get_dns_name: Will return with the DNS _name for the IP scanned
        :param contain_random_data: Will not just send empty packets like the default
        :param randomise_targets: Will go through the targets provided in a random order
        :param source_address: Changes where the ping says it came from
        :param verbose: Only really effects the ping count command. Swaps output from RTTimes to Statistics

        :return: list of IP's that were seen to be alive
        """

        command = ["fping", "-a", "-I ", interface]

        # Adding Flags
        if ping_count > 0:
            if verbose:
                command += ["-D", "--count=" + str(ping_count)]
            else:
                command += ["--vcount=" + str(ping_count)]

        if get_dns_name:
            command += ["-n"]

        if randomise_targets:
            command += ["--random"]

        if contain_random_data:
            command += ["-R"]

        if source_address is not "self":
            if IpValidator.is_valid_ipv4_address(source_address):
                command += ["--src=" + source_address]
            else:
                self.enumerate.debug("Error: The redirection should be to a IPv4", color=Format.color_warning)
                return False

        # Adding Targets
        if type(target) is list:
            if all_ips_from_dns:
                for item in target:
                    if not re.search("\A[a-z0-9]*\.[a-z0-9]*\.[a-z0-9]*", item.lower()):
                        self.enumerate.debug("Error: Target in list is not a valid IP or hostname"
                                             "(Does not accept ranges here)", color=Format.color_warning)
                        return False
            else:
                for item in target:
                    if not IpValidator.is_valid_ipv4_address(item):
                        self.enumerate.debug("Error: Target in list is not a valid IP (Does not accept ranges here)",
                                             color=Format.color_warning)
                        return False

            command += target

        elif IpValidator.is_valid_ipv4_address(str(target)):
            command += [target]

        elif IpValidator.is_valid_ipv4_address(str(target), iprange=True):
            command += ["-g", target]

        elif re.search("\A[a-z0-9]*\.[a-z0-9]*\.[a-z0-9]*\Z", str(target).lower()) and all_ips_from_dns:
            command += ["-m", target]
        else:
            self.enumerate.debug("Error: Target is not a valid IP, Range or list", color=Format.color_warning)
            return False

        if ping_count > 0:
            output = subprocess.run(command, stderr=subprocess.PIPE).stderr.decode("utf-8").strip().split("\n")
        else:
            output = subprocess.run(command, stdout=subprocess.PIPE).stdout.decode("utf-8").strip().split("\n")

        if not output:
            return False

        if source_address is not "self":
            return False

        if ping_count > 0:
            final_out = [[]]

            if verbose:
                # This is not working. It cuts the min/avg/max section of the out and I cant be arsed fixing it
                for line in output:
                    final_out += [line.split(" : ")]
            else:
                for line in output:
                    temp = line.split(" : ")
                    temp[1] = temp[1].split()
                    final_out += [temp]

            del final_out[0]

            self.enumerate.debug("check_target_is_alive: Output generated successfully", color=Format.color_success)
            return final_out

        self.enumerate.debug("check_target_is_alive: Output generated successfully", color=Format.color_success)
        return output

    def get_route_to_target(self, target, interface="usb0", bypass_routing_tables=False, hop_back_checks=True,
                            map_host_names=True, original_out=False):
        """
        Makes use of the traceroute command.
        No default flags are in use that the user cannot access via output

        Args:
        :param target: takes in a IPv4 target (Cannot Take a list)
        :param interface: Defaults to usb0 but can make use of any interface that is available
        :param bypass_routing_tables: Allows for traceroute to take the most direct approach bypassing routing tables
        :param hop_back_checks: Confirms that packets taken by the response follow the same path
        :param map_host_names: In the event that mapping host names to IP makes noise this can be disabled
        :param original_out: If the user wants the original command output this should be changed to true

        :return: 2 list of max 30 items with ips for each hop to the target and returning
                 List to target is a list of strings and List from target containing lists of strings
                 Bad hops / no information is signaled as '*'
        """
        command = ["traceroute", "-i", interface]  # start with command items that are required

        # Add command arguments where appropriate
        if bypass_routing_tables:
            command += ["-r"]

        if hop_back_checks:
            command += ["--back"]

        if not map_host_names:
            command += ["-n"]

        if type(target) is str:
            if IpValidator.is_valid_ipv4_address(target):
                command += [target]
        else:
            self.enumerate.debug("Error: Wrong type - ip should be <string>", color=Format.color_warning)
            return False

        # Running command
        output = subprocess.run(command, stdout=subprocess.PIPE).stdout.decode("utf-8")

        if original_out:  # If user doesnt want output parsed
            return output

        # Parsing output
        output = output.splitlines()

        del output[0]

        route_out = []
        route_back = []

        for line in output:
            line = line.split()
            del line[0]

            results = []  # init var to store current results
            if map_host_names:
                for item in line:
                    # If item looks like a domain or the first three octets of an IP address
                    if re.search("[a-z0-9]*\.[a-z0-9]*\.[a-z0-9]*",
                                 item.lower()):  # Would compiling a re be better here?
                        results += [item.strip("\(\)")]  # Remove any brackets and add to results for this line
            else:
                for item in line:
                    if IpValidator.is_valid_ipv4_address(item):
                        results += [item]

            if len(results) is 1:
                route_out += [results]  # Add results from this line
                route_back += []
            elif len(results) is not 0:
                route_out += [results[0]]
                route_back += [results[1:]]
            else:
                route_out += ["*"]
                route_back += [["*"]]

        if type(route_out[0]) is list:
            route_out[0] = route_out[0][0]

        self.enumerate.debug("get_route_to_target: Output generated successfully", color=Format.color_success)
        return route_out, route_back

    def get_targets_via_arp(self, target, interface="usb0", source_ip="self", target_is_file=False,
                            original_out=False, randomise_targets=False):
        """
        Makes use of the arp-scan command.
        By default makes use of the verbose and retry flags.

        Target can be a list of IP's or a single IP.
            This allows for passing in the lists (such as that which the configs stores)
        :param target: IPv4 address(s) e.g "192.168.0.1", "192.168.0.0/24", ["192.168.0.1", "192.168.0.2"]

        :param interface: String value for interface, can make use of any interface that is available
                Defaults to "usb0"
        :param source_ip: String value that can be changed send packets with source being another address.
                Defaults to "self"
        :param target_is_file: Binary value for when the user wishes to use a file containing addresses.
                Defaults False
        :param original_out: Binary value for whether the command gives out the command output without parsing.
                Defaults False
        :param randomise_targets: Binary Value for targets where they should not be scanned in the order given.
                Defaults False

        :return: list of lists containing IP, MAC address and Adapter _name


        """
        command = ["sudo", "arp-scan", "-v", "-I", interface, "-r", "3"]

        if randomise_targets:
            command += ['-R']

        if source_ip is not "self" and IpValidator.is_valid_ipv4_address(source_ip):
            command += ["-s", source_ip]

        if target_is_file is True:
            if target is list:
                self.enumerate.debug("Error: A list of files cannot be scanned", color=Format.color_warning)
                return False

            command += ["-f", target]  # The target in this case should be the path to a target list file

        else:  # if target is not a file
            if type(target) is list:
                for current in target:
                    if not IpValidator.is_valid_ipv4_address(current, iprange=True):
                        self.enumerate.debug("Error: Target %s in list is not a valid IP" % target,
                                             color=Format.color_warning)
                        return False

                command += target

            elif type(target) is str:  # if target is just an IP
                if not IpValidator.is_valid_ipv4_address(target, iprange=True):
                    self.enumerate.debug("Error: Target is not a valid IP or Range", color=Format.color_warning)
                    return False

                command += [target]

            else:
                self.enumerate.debug("Error: Target is not a string or list")
                return False

        output = subprocess.run(command, stdout=subprocess.PIPE, shell=False).stdout.decode("utf-8")

        self.enumerate.debug("get_targets_via_arp output captured: %s" % True if output else False)

        if original_out is True:
            return output

        output = output.splitlines()

        self.enumerate.debug("get_targets_via_arp generating results...")
        # Removing generalised information out
        try:
            del output[0:2]
            del output[-3:]

            outlist = []

            for line in output:
                # Splits where literal tabs exist (between the IP, MAC and Adapter Name)
                outlist += [line.split("\t")]
        except Exception as Err:
            self.enumerate.debug("get_targets_via_arp Error: %s" % Err, color=Format.color_warning)
            return False

        self.enumerate.debug("get_targets_via_arp: Output generated successfully", color=Format.color_success)
        return outlist  # Sorting via IP would be nice

    # Extracting the information we need is going to look disguisting, try to keep each tool in a single def.
    # e.g. def for nbtstat, def for nmap, def for net etc...
