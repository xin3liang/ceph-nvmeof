import pytest
from control.server import GatewayServer
import socket
from control.cli import main as cli
from control.cli import main_test as cli_test
from control.cephutils import CephUtils
from control.utils import GatewayUtils
from control.config import GatewayConfig
import grpc
from control.proto import gateway_pb2 as pb2
from control.proto import gateway_pb2_grpc as pb2_grpc
import os
import os.path

image = "mytestdevimage"
pool = "rbd"
subsystem = "nqn.2016-06.io.spdk:cnode1"
subsystem2 = "nqn.2016-06.io.spdk:cnode2"
hostnqn1 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7eb"
hostnqn2 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7ec"
hostnqn4 = "nqn.2014-08.org.nvmexpress:uuid:6488a49c-dfa3-11d4-ac31-b232c6c68a8a"
hostnqn5 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7ef"
hostnqn6 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7f0"
hostnqn7 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7f1"
hostnqn8 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7f2"
hostnqn9 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7f3"
hostnqn10 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7f4"
hostnqn11 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7f5"
hostnqn12 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7f6"
hostnqn13 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7f7"
hostnqn14 = "nqn.2014-08.org.nvmexpress:uuid:22207d09-d8af-4ed2-84ec-a6d80b0cf7f8"

discovery_nqn = "nqn.2014-08.org.nvmexpress.discovery"

hostdhchap1 = "DHHC-1:00:MWPqcx1Ug1debg8fPIGpkqbQhLcYUt39k7UWirkblaKEH1kE:"
hostdhchap2 = "DHHC-1:00:ojmm6ISA2DBpZEldEJqJvA1/cAl1wDmeolS0fCIn2qZpK0b7gpx3qu76yHpjlOOXNyjqf0oFYCWxUqkXGN2xEBOVxoA=:"
hostdhchap4 = "DHHC-1:01:Ei7kUrD7iyrjzXDwIZ666sSPBswUk4wDjSQtodytVB5YiBru:"
hostdhchap5 = "DHHC-1:03:6EKZcEL86u4vzTE8sCETvskE3pLKE+qOorl9QxrRfLvfOEQ5GvqCzM41U8fFVAz1cs+T14PjSpd1J641rfeCC1x2VNg=:"
hostdhchap6 = "DHHC-1:02:ULMaRuJ40ui58nK4Qk5b0J89G3unbGb8mBUbt/XSrf18PBPvyL3sivZOINNh2o/fPpXbGg==:"
hostdhchap7 = "DHHC-1:01:x7ecfGgIdOEl+J5cJ9JcZHOS2By2Me6eDJUnrsT9MVrCWRYV:"
hostdhchap8 = "DHHC-1:01:eNNXGjidEHHStbUi2Gmpps0JcnofReFfy+NaulguGgt327hz:"

hostpsk1 = "NVMeTLSkey-1:01:YzrPElk4OYy1uUERriPwiiyEJE/+J5ckYpLB+5NHMsR2iBuT:"

host_name = socket.gethostname()
addr = "127.0.0.1"
config = "ceph-nvmeof.conf"

@pytest.fixture(scope="module")
def gateway(config):
    """Sets up and tears down Gateway"""

    addr = config.get("gateway", "addr")
    port = config.getint("gateway", "port")
    config.config["gateway-logs"]["log_level"] = "debug"
    config.config["gateway"]["group"] = ""
    ceph_utils = CephUtils(config)

    with GatewayServer(config) as gateway:

        # Start gateway
        gateway.gw_logger_object.set_log_level("debug")
        ceph_utils.execute_ceph_monitor_command("{" + f'"prefix":"nvme-gw create", "id": "{gateway.name}", "pool": "{pool}", "group": ""' + "}")
        gateway.serve()

        # Bind the client and Gateway
        channel = grpc.insecure_channel(f"{addr}:{port}")
        yield gateway.gateway_rpc

        # Stop gateway
        gateway.server.stop(grace=1)
        gateway.gateway_rpc.gateway_state.delete_state()

def test_setup(caplog, gateway):
    gw = gateway
    caplog.clear()
    cli(["subsystem", "add", "--subsystem", subsystem, "--no-group-append"])
    assert f"create_subsystem {subsystem}: True" in caplog.text
    caplog.clear()
    cli(["namespace", "add", "--subsystem", subsystem, "--rbd-pool", pool, "--rbd-image", image, "--rbd-create-image", "--size", "16MB"])
    assert f"Adding namespace 1 to {subsystem}: Successful" in caplog.text
    caplog.clear()
    cli(["subsystem", "add", "--subsystem", subsystem2, "--dhchap-key", hostdhchap6])
    assert f"create_subsystem {subsystem2}: True" in caplog.text

def test_create_secure(caplog, gateway):
    caplog.clear()
    cli(["listener", "add", "--subsystem", subsystem, "--host-name", host_name, "-a", addr, "-s", "5001", "--secure"])
    assert f"Adding {subsystem} listener at {addr}:5001: Successful" in caplog.text
    caplog.clear()
    cli(["host", "add", "--subsystem", subsystem, "--host-nqn", hostnqn1, "--dhchap-key", hostdhchap1])
    assert f"Adding host {hostnqn1} to {subsystem}: Successful" in caplog.text
    assert f"Host {hostnqn1} has a DH-HMAC-CHAP key but subsystem {subsystem} has no key, a unidirectional authentication will be used" in caplog.text
    caplog.clear()
    cli(["host", "add", "--subsystem", subsystem, "--host-nqn", hostnqn2, "--dhchap-key", hostdhchap2])
    assert f"Adding host {hostnqn2} to {subsystem}: Successful" in caplog.text
    assert f"Host {hostnqn2} has a DH-HMAC-CHAP key but subsystem {subsystem} has no key, a unidirectional authentication will be used" in caplog.text
    caplog.clear()
    cli(["host", "add", "--subsystem", subsystem, "--host-nqn", hostnqn4, "--dhchap-key", hostdhchap4])
    assert f"Adding host {hostnqn4} to {subsystem}: Successful" in caplog.text
    assert f"Host {hostnqn4} has a DH-HMAC-CHAP key but subsystem {subsystem} has no key, a unidirectional authentication will be used" in caplog.text

def test_create_not_secure(caplog, gateway):
    caplog.clear()
    cli(["listener", "add", "--subsystem", subsystem, "--host-name", host_name, "-a", addr, "-s", "5002"])
    assert f"Adding {subsystem} listener at {addr}:5002: Successful" in caplog.text
    caplog.clear()
    cli(["host", "add", "--subsystem", subsystem, "--host-nqn", hostnqn6])
    assert f"Adding host {hostnqn6} to {subsystem}: Successful" in caplog.text
    caplog.clear()
    cli(["host", "add", "--subsystem", subsystem, "--host-nqn", hostnqn7])
    assert f"Adding host {hostnqn7} to {subsystem}: Successful" in caplog.text

def test_create_secure_list(caplog, gateway):
    caplog.clear()
    rc = 0
    try:
        cli(["host", "add", "--subsystem", subsystem, "--host-nqn", hostnqn8, hostnqn9, hostnqn10, "--dhchap-key", hostdhchap1])
    except SystemExit as sysex:
        rc = int(str(sysex))
        pass
    assert rc == 2
    assert f"error: Can't have more than one host NQN when DH-HMAC-CHAP keys are used" in caplog.text

def test_create_secure_no_key(caplog, gateway):
    caplog.clear()
    rc = 0
    try:
        cli(["host", "add", "--subsystem", subsystem, "--host-nqn", hostnqn5, "--dhchap-key"])
    except SystemExit as sysex:
        rc = int(str(sysex))
        pass
    assert rc == 2
    assert f"error: argument --dhchap-key/-k: expected one argument" in caplog.text

def test_dhchap_subsystem_key(caplog, gateway):
    caplog.clear()
    cli(["host", "add", "--subsystem", subsystem2, "--host-nqn", hostnqn11, "--dhchap-key", hostdhchap5])
    assert f"Adding host {hostnqn11} to {subsystem2}: Successful" in caplog.text

def test_list_dhchap_hosts(caplog, gateway):
    caplog.clear()
    hosts = cli_test(["host", "list", "--subsystem", subsystem])
    found = 0
    assert len(hosts.hosts) == 5
    for h in hosts.hosts:
        if h.nqn == hostnqn1:
            found += 1
            assert h.use_dhchap
        elif h.nqn == hostnqn2:
            found += 1
            assert h.use_dhchap
        elif h.nqn == hostnqn4:
            found += 1
            assert h.use_dhchap
        elif h.nqn == hostnqn6:
            found += 1
            assert not h.use_dhchap
        elif h.nqn == hostnqn7:
            found += 1
            assert not h.use_dhchap
        else:
            assert False
    assert found == 5

    caplog.clear()
    hosts = cli_test(["host", "list", "--subsystem", subsystem2])
    found = 0
    assert len(hosts.hosts) == 1
    for h in hosts.hosts:
        if h.nqn == hostnqn11:
            found += 1
            assert h.use_dhchap
        else:
            assert False
    assert found == 1

def test_allow_any_host_with_dhchap(caplog, gateway):
    caplog.clear()
    rc = 0
    try:
        cli(["host", "add", "--subsystem", subsystem, "--host-nqn", "*", "--dhchap-key", hostdhchap1])
    except SystemExit as sysex:
        rc = int(str(sysex))
        pass
    assert rc == 2
    assert f"error: DH-HMAC-CHAP key is only allowed for specific hosts" in caplog.text

def test_dhchap_controller_with_no_dhchap_key(caplog, gateway):
    caplog.clear()
    cli(["host", "add", "--subsystem", subsystem2, "--host-nqn", hostnqn10])
    assert f"Failure adding host {hostnqn10} to {subsystem2}: Host must have a DH-HMAC-CHAP key if the subsystem has one" in caplog.text

def test_list_listeners(caplog, gateway):
    caplog.clear()
    listeners = cli_test(["listener", "list", "--subsystem", subsystem])
    assert len(listeners.listeners) == 2
    found = 0
    for l in listeners.listeners:
        if l.trsvcid == 5001:
            found += 1
            assert l.secure
        elif l.trsvcid == 5002:
            found += 1
            assert not l.secure
        else:
            assert False
    assert found == 2

def test_add_key_to_host(caplog, gateway):
    caplog.clear()
    found = False
    hosts = cli_test(["host", "list", "--subsystem", subsystem])
    for h in hosts.hosts:
        if h.nqn == hostnqn7:
            found = True
            assert not h.use_dhchap
            break
    assert found
    caplog.clear()
    cli(["host", "change_key", "--subsystem", subsystem, "--host-nqn", hostnqn7, "--dhchap-key", hostdhchap6])
    assert f"Changing key for host {hostnqn7} on subsystem {subsystem}: Successful" in caplog.text
    assert f"Host {hostnqn7} has a DH-HMAC-CHAP key but subsystem {subsystem} has no key, a unidirectional authentication will be used" in caplog.text
    caplog.clear()
    found = False
    hosts = cli_test(["host", "list", "--subsystem", subsystem])
    for h in hosts.hosts:
        if h.nqn == hostnqn7:
            found = True
            assert h.use_dhchap
            break
    assert found

def change_key_to_all_hosts(caplog, gateway):
    caplog.clear()
    rc = 0
    try:
        cli(["host", "change_key", "--subsystem", subsystem, "--host-nqn", "*", "--dhchap-key", hostdhchap1])
    except SystemExit as sysex:
        rc = int(str(sysex))
        pass
    assert rc == 2
    assert f"error: Can't change keys for host NQN '*', please use a real NQN" in caplog.text

def change_key_for_host(caplog, gateway):
    caplog.clear()
    cli(["host", "change_key", "--subsystem", subsystem, "--host-nqn", hostnqn7, "--dhchap-key", hostdhchap1])
    assert f"Changing keys for host {hostnqn7} on subsystem {subsystem}: Successful" in caplog.text
    assert f"Host {hostnqn7} has a DH-HMAC-CHAP key but subsystem {subsystem} has no key, a unidirectional authentication will be used" in caplog.text

def test_change_key_with_psk(caplog, gateway):
    caplog.clear()
    cli(["host", "add", "--subsystem", subsystem, "--host-nqn", hostnqn12, "--psk", hostpsk1])
    assert f"Adding host {hostnqn12} to {subsystem}: Successful" in caplog.text
    caplog.clear()
    cli(["host", "change_key", "--subsystem", subsystem, "--host-nqn", hostnqn12, "--dhchap-key", hostdhchap7])
    assert f"Changing key for host {hostnqn12} on subsystem {subsystem}: Successful" in caplog.text
    assert f"Host {hostnqn12} has a DH-HMAC-CHAP key but subsystem {subsystem} has no key, a unidirectional authentication will be used" in caplog.text

def test_change_key_host_not_exist(caplog, gateway):
    caplog.clear()
    cli(["host", "change_key", "--subsystem", subsystem, "--host-nqn", hostnqn13, "--dhchap-key", "junk"])
    assert f"Failure changing DH-HMAC-CHAP key for host {hostnqn13} on subsystem {subsystem}: Can't find host on subsystem" in caplog.text

def test_change_key_host_on_discovery(caplog, gateway):
    caplog.clear()
    cli(["host", "change_key", "--subsystem", discovery_nqn, "--host-nqn", hostnqn12, "--dhchap-key", "junk"])
    assert f"Failure changing DH-HMAC-CHAP key for host {hostnqn12} on subsystem {discovery_nqn}: Can't use a discovery NQN as subsystem's" in caplog.text
    caplog.clear()
    cli(["host", "change_key", "--subsystem", subsystem, "--host-nqn", discovery_nqn, "--dhchap-key", "junk"])
    assert f"Failure changing DH-HMAC-CHAP key for host {discovery_nqn} on subsystem {subsystem}: Can't use a discovery NQN as host's" in caplog.text

def test_change_key_host_invalid_nqn(caplog, gateway):
    caplog.clear()
    badsubsystem = subsystem.replace("-", "_")
    cli(["host", "change_key", "--subsystem", badsubsystem, "--host-nqn", hostnqn12, "--dhchap-key", "junk"])
    assert f"Failure changing DH-HMAC-CHAP key for host {hostnqn12} on subsystem {badsubsystem}: Invalid subsystem NQN \"{badsubsystem}\", contains invalid characters" in caplog.text
    bad_hostnqn = hostnqn12.replace("-", "_")
    caplog.clear()
    cli(["host", "change_key", "--subsystem", subsystem, "--host-nqn", bad_hostnqn, "--dhchap-key", "junk"])
    assert f"Failure changing DH-HMAC-CHAP key for host {bad_hostnqn} on subsystem {subsystem}: Invalid host NQN \"{bad_hostnqn}\", contains invalid characters" in caplog.text
    caplog.clear()
    cli(["host", "change_key", "--subsystem", "badnqn", "--host-nqn", hostnqn12, "--dhchap-key", "junk"])
    assert f"Failure changing DH-HMAC-CHAP key for host {hostnqn12} on subsystem badnqn: NQN \"badnqn\" is too short, minimal length is 11" in caplog.text
    caplog.clear()
    cli(["host", "change_key", "--subsystem", subsystem, "--host-nqn", "badnqn", "--dhchap-key", "junk"])
    assert f"Failure changing DH-HMAC-CHAP key for host badnqn on subsystem {subsystem}: NQN \"badnqn\" is too short, minimal length is 11" in caplog.text

def test_change_key_host_on_all_hosts(caplog, gateway):
    caplog.clear()
    rc = 0
    try:
        cli(["host", "change_key", "--subsystem", subsystem, "--host-nqn", "*", "--dhchap-key", "junk"])
    except SystemExit as sysex:
        rc = int(str(sysex))
        pass
    assert "Can't change keys for host NQN '*', please use a real NQN" in caplog.text
    assert rc == 2

def test_add_host_with_key_host_list(caplog, gateway):
    caplog.clear()
    rc = 0
    try:
        cli(["host", "add", "--subsystem", subsystem, "--host-nqn", hostnqn13, hostnqn14, "--dhchap-key", "junk"])
    except SystemExit as sysex:
        rc = int(str(sysex))
        pass
    assert "Can't have more than one host NQN when DH-HMAC-CHAP keys are used" in caplog.text
    assert rc == 2

def test_set_subsystem_key_with_non_key_hosts(caplog, gateway):
    caplog.clear()
    cli(["subsystem", "change_key", "--subsystem", subsystem, "--dhchap-key", hostdhchap8])
    assert f"Failure changing DH-HMAC-CHAP key for subsystem {subsystem}: Can't set a subsystem's DH-HMAC-CHAP key when it has hosts with no key, like host " in caplog.text

def test_change_subsystem_key(caplog, gateway):
    caplog.clear()
    cli(["subsystem", "change_key", "--subsystem", subsystem2, "--dhchap-key", hostdhchap8])
    assert f"Changing key for subsystem {subsystem2}: Successful" in caplog.text
    assert f"Received request to change inband authentication key for host {hostnqn11} on subsystem {subsystem2}" in caplog.text
