; benchmark generated from python API
(set-info :status unknown)
(declare-fun approval_authorized () Bool)
(declare-fun attempt_to_approve_own_pull_request () Bool)
(declare-fun ENABLE_SOD_1301 () Bool)
(declare-fun SCENARIO_repository_owner_attempts_to_approve_own_pull_request () Bool)
(declare-fun merge_authorized () Bool)
(declare-fun ENABLE_SOD_1302 () Bool)
(assert
 (let (($x6 (and attempt_to_approve_own_pull_request)))
 (=> (and ENABLE_SOD_1301 $x6) (and (not approval_authorized)))))
(assert
 (let (($x6 (and attempt_to_approve_own_pull_request)))
 (=> SCENARIO_repository_owner_attempts_to_approve_own_pull_request $x6)))
(assert
 (let (($x6 (and attempt_to_approve_own_pull_request)))
 (=> (and ENABLE_SOD_1302 $x6) (and approval_authorized merge_authorized))))
(assert
 (let (($x6 (and attempt_to_approve_own_pull_request)))
(=> SCENARIO_repository_owner_attempts_to_approve_own_pull_request $x6)))

(check-sat-assuming (ENABLE_SOD_1301 ENABLE_SOD_1302 SCENARIO_repository_owner_attempts_to_approve_own_pull_request))
(get-unsat-core)
