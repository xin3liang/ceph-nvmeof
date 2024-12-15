#
#  Copyright (c) 2024 International Business Machines
#  All rights reserved.
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
#  Authors: leonidc@il.ibm.com
#

#import uuid
import errno
import threading
import time
import json
import re
from .utils import GatewayLogger
from .config import GatewayConfig
from .proto import gateway_pb2 as pb2

class Rebalance:
    """Miscellaneous functions which do rebalance of ANA groups
    """

    def __init__(self, gateway_service):
        self.logger = gateway_service.logger
        self.gw_srv = gateway_service
        self.ceph_utils = gateway_service.ceph_utils
        self.rebalance_period_sec              = gateway_service.config.getint_with_default("gateway",  "rebalance_period_sec", 7)
        self.rebalance_max_ns_to_change_lb_grp = gateway_service.config.getint_with_default("gateway", "max_ns_to_change_lb_grp", 8)
        self.auto_rebalance = threading.Thread(target=self.auto_rebalance_task, daemon=True)
        self.auto_rebalance.start() #start the thread

    def auto_rebalance_task(self ):
        """Periodically calls for auto rebalance."""
        while (self.rebalance_period_sec > 0):
            for i in range(self.rebalance_max_ns_to_change_lb_grp):
                try:
                    rc = self.gw_srv.execute_grpc_function(self.rebalance_logic, None, "context")
                    if rc == 1:
                        self.logger.debug(f"Nothing found for rebalance, break at {i} iteration")
                        break
                except Exception:
                        self.logger.exception(f"Exception in auto rebalance")
                        raise
                time.sleep(0.01) #release lock for 10ms after rebalancing each 1 NS
            time.sleep(self.rebalance_period_sec)

    def find_min_loaded_group(self, grp_list)->int:
        min_load = 2000
        chosen_ana_group = 0
        for ana_grp in self.gw_srv.ana_grp_ns_load :
            if  ana_grp  in grp_list :
                  if self.gw_srv.ana_grp_ns_load[ana_grp] <=  min_load:
                      min_load = self.gw_srv.ana_grp_ns_load[ana_grp]
                      chosen_ana_group = ana_grp
        min_load = 2000
        for nqn in self.gw_srv.ana_grp_subs_load[chosen_ana_group] :
            if self.gw_srv.ana_grp_subs_load[chosen_ana_group][nqn] <  min_load:
                min_load = self.gw_srv.ana_grp_subs_load[chosen_ana_group][nqn]
                chosen_nqn = nqn
        return chosen_ana_group, chosen_nqn

    def find_min_loaded_group_in_subsys(self, nqn, grp_list)->int:
        min_load = 2000
        chosen_ana_group = 0
        for ana_grp in grp_list :
            if  self.gw_srv.ana_grp_ns_load[ana_grp] == 0:
                self.gw_srv.ana_grp_subs_load[ana_grp][nqn] = 0
                return 0, ana_grp
        for ana_grp in self.gw_srv.ana_grp_subs_load :
            if  ana_grp  in grp_list :
                if nqn in self.gw_srv.ana_grp_subs_load[ana_grp]:
                    if self.gw_srv.ana_grp_subs_load[ana_grp][nqn] <=  min_load:
                        min_load = self.gw_srv.ana_grp_subs_load[ana_grp][nqn]
                        chosen_ana_group = ana_grp
                else: #still  no load on this ana and subs
                    chosen_ana_group = ana_grp
                    self.gw_srv.ana_grp_subs_load[chosen_ana_group][nqn] = 0
                    min_load = 0
                    break
        return min_load, chosen_ana_group

    # 1. Not allowed to perform regular rebalance when scale_down rebalance is ongoing
    # 2. Monitor each time defines what GW is responsible for regular rebalance(fairness logic), so there will not be collisions between the GWs 
    # and reballance results will be accurate. Monitor in nvme-gw show response publishes the index of ANA group that is currently responsible for rebalance
    def rebalance_logic(self, request, context)->int:
        worker_ana_group = self.ceph_utils.get_rebalance_ana_group()
        self.logger.debug(f"Called rebalance logic: current rebalancing ana group {worker_ana_group}")
        ongoing_scale_down_rebalance = False
        grps_list = self.ceph_utils.get_number_created_gateways(self.gw_srv.gateway_pool, self.gw_srv.gateway_group)
        if not self.ceph_utils.is_rebalance_supported():
            self.logger.info(f"Auto rebalance is not supported with the curent ceph version")
            return 1
        for ana_grp in self.gw_srv.ana_grp_state:
            if self.gw_srv.ana_grp_ns_load[ana_grp] !=  0  : #internally valid group
                if ana_grp not in grps_list:  #monitor considers it invalid since GW owner was deleted
                    ongoing_scale_down_rebalance = True
                    self.logger.info(f"Scale-down rebalance is ongoing for ANA group  {ana_grp} current load {self.gw_srv.ana_grp_ns_load[ana_grp]}")
                    break
        num_active_ana_groups = len(grps_list)
        for ana_grp in self.gw_srv.ana_grp_state:
            if self.gw_srv.ana_grp_state[ana_grp] == pb2.ana_state.OPTIMIZED :
                if ana_grp not in grps_list:
                    self.logger.info(f"Found optimized ana group {ana_grp} that handles the group of deleted GW."
                                     f"Number NS in group {self.gw_srv.ana_grp_ns_load[ana_grp]} - Start NS rebalance")
                    if self.gw_srv.ana_grp_ns_load[ana_grp] >= self.rebalance_max_ns_to_change_lb_grp:
                       num = self.rebalance_max_ns_to_change_lb_grp
                    else:
                       num = self.gw_srv.ana_grp_ns_load[ana_grp]
                    if num > 0 :
                        min_ana_grp, chosen_nqn = self.find_min_loaded_group(grps_list)
                        self.logger.info(f"Start rebalance (scale down)  destination ana group {min_ana_grp}, subsystem {chosen_nqn}")
                        self.ns_rebalance(context, ana_grp, min_ana_grp, 1, "0")#scale down rebalance
                        return 0
                    else :
                        self.logger.info(f"warning: empty group {ana_grp} of Deleting GW still appears Optimized")
                        return 1
                else :
                    if not ongoing_scale_down_rebalance  and  (self.gw_srv.ana_grp_state[worker_ana_group] == pb2.ana_state.OPTIMIZED) :
                    # if  my optimized ana group == worker-ana-group or worker-ana-group is also in optimized state on this GW machine
                        for nqn in self.gw_srv.ana_grp_subs_load[ana_grp] : #need to search  all nqns not only inside the current load
                            num_ns_in_nqn = self.gw_srv.subsystem_nsid_bdev_and_uuid.get_namespace_count(nqn, None, 0)
                            target_subs_per_ana = num_ns_in_nqn/num_active_ana_groups
                            self.logger.debug(f"loop: nqn {nqn} ana group {ana_grp} load {self.gw_srv.ana_grp_subs_load[ana_grp][nqn]}, "
                                              f"num-ns in nqn {num_ns_in_nqn}, target_subs_per_ana {target_subs_per_ana} ")
                            if self.gw_srv.ana_grp_subs_load[ana_grp][nqn] > target_subs_per_ana:
                                self.logger.debug(f"max-nqn load {self.gw_srv.ana_grp_subs_load[ana_grp][nqn]} nqn {nqn} ")
                                min_load, min_ana_grp = self.find_min_loaded_group_in_subsys(nqn, grps_list)
                                if (
                                    (self.gw_srv.ana_grp_subs_load[min_ana_grp][nqn] + 1) <= target_subs_per_ana
                                    or (self.gw_srv.ana_grp_subs_load[min_ana_grp][nqn] + 1) == (self.gw_srv.ana_grp_subs_load[ana_grp][nqn] - 1)
                                   ):
                                       self.logger.info(f"Start rebalance (regular) in subsystem {nqn}, dest ana {min_ana_grp}, dest ana load per subs {min_load}")
                                       self.ns_rebalance(context, ana_grp, min_ana_grp, 1, nqn) #regular rebalance
                                       return 0
                                else:
                                    self.logger.debug(f"Found min loaded subsystem {nqn}, ana {min_ana_grp}, load {min_load} does not fit rebalance criteria!")
                                    continue
        return 1

    def ns_rebalance(self, context, ana_id, dest_ana_id, num, subs_nqn) ->int:
        now = time.time()
        num_rebalanced = 0
        self.logger.info(f"== rebalance started == for subsystem {subs_nqn}, anagrp {ana_id}, destination anagrp {dest_ana_id}, num ns {num} time {now} ")
        ns_list = self.gw_srv.subsystem_nsid_bdev_and_uuid.get_all_namespaces_by_ana_group_id(ana_id)
        self.logger.debug(f"Doing loop on {ana_id} ")
        for nsid, subsys in ns_list:
            self.logger.debug(f"nsid {nsid} for nqn {subsys} to rebalance:")
            if subsys == subs_nqn or subs_nqn == "0":
               self.logger.info(f"nsid for change_load_balancing  : {nsid}, {subsys}, anagrpid: {ana_id}")
               change_lb_group_req = pb2.namespace_change_load_balancing_group_req(subsystem_nqn=subsys, nsid= nsid, anagrpid=dest_ana_id, auto_lb_logic=True)
               ret = self.gw_srv.namespace_change_load_balancing_group_safe(change_lb_group_req, context)
               self.logger.debug(f"ret namespace_change_load_balancing_group  {ret}")
               num_rebalanced += 1
               if num_rebalanced >= num :
                 self.logger.info(f"== Completed rebalance in {time.time() - now } sec for {num} namespaces from anagrp {ana_id} to {dest_ana_id} ")
                 return 0
        return 0
