; benchmark generated from python API
(set-info :status unknown)
(declare-fun dashboard_access_granted () Bool)
(declare-fun dashboard_access_requested () Bool)
(declare-fun ENABLE_ACCESS_1001 () Bool)
(declare-fun SCENARIO_dashboard_access_requested_by_registered_user () Bool)
(declare-fun ENABLE_ACCESS_1002 () Bool)
(declare-fun order_confirmation_email_sent () Bool)
(declare-fun order_submitted () Bool)
(declare-fun ENABLE_EMAIL_2001 () Bool)
(declare-fun SCENARIO_order_submitted_by_customer () Bool)
(declare-fun ENABLE_EMAIL_2002 () Bool)
(declare-fun account_locked () Bool)
(declare-fun login_attempt_count () Int)
(declare-fun ENABLE_VAC_3001 () Bool)
(declare-fun SCENARIO_login_attempt_count_out_of_bounds () Bool)
(declare-fun profile_update_recorded () Bool)
(declare-fun profile_updated () Bool)
(declare-fun ENABLE_SAFE_4001 () Bool)
(declare-fun SCENARIO_profile_updated_by_customer () Bool)
(declare-fun startup_event_recorded () Bool)
(declare-fun application_started () Bool)
(declare-fun ENABLE_SAFE_4002 () Bool)
(declare-fun SCENARIO_application_started_successfully () Bool)
(assert
 (=> (and ENABLE_ACCESS_1001 (and dashboard_access_requested)) (and dashboard_access_granted)))
(assert
 (let (($x6 (and dashboard_access_requested)))
 (=> SCENARIO_dashboard_access_requested_by_registered_user $x6)))
(assert
 (let (($x6 (and dashboard_access_requested)))
 (=> (and ENABLE_ACCESS_1002 $x6) (and (not dashboard_access_granted)))))
(assert
 (let (($x6 (and dashboard_access_requested)))
 (=> SCENARIO_dashboard_access_requested_by_registered_user $x6)))
(assert
 (=> (and ENABLE_EMAIL_2001 (and order_submitted)) (and order_confirmation_email_sent)))
(assert
 (let (($x44 (and order_submitted)))
 (=> SCENARIO_order_submitted_by_customer $x44)))
(assert
 (=> (and ENABLE_EMAIL_2002 (and order_submitted)) (and (not order_confirmation_email_sent))))
(assert
 (let (($x44 (and order_submitted)))
 (=> SCENARIO_order_submitted_by_customer $x44)))
(assert
 (let (($x72 (and (< 10 login_attempt_count) (> 3 login_attempt_count))))
 (=> (and ENABLE_VAC_3001 $x72) (and account_locked))))
(assert
 (let (($x72 (and (< 10 login_attempt_count) (> 3 login_attempt_count))))
 (=> SCENARIO_login_attempt_count_out_of_bounds $x72)))
(assert
 (=> (and ENABLE_SAFE_4001 (and profile_updated)) (and profile_update_recorded)))
(assert
 (let (($x90 (and profile_updated)))
 (=> SCENARIO_profile_updated_by_customer $x90)))
(assert
 (=> (and ENABLE_SAFE_4002 (and application_started)) (and startup_event_recorded)))
(assert
 (let (($x104 (and application_started)))
(=> SCENARIO_application_started_successfully $x104)))

(check-sat-assuming (ENABLE_ACCESS_1001 ENABLE_ACCESS_1002 ENABLE_EMAIL_2001 ENABLE_EMAIL_2002 ENABLE_VAC_3001 ENABLE_SAFE_4001 ENABLE_SAFE_4002 SCENARIO_dashboard_access_requested_by_registered_user SCENARIO_order_submitted_by_customer SCENARIO_login_attempt_count_out_of_bounds SCENARIO_profile_updated_by_customer SCENARIO_application_started_successfully))
(get-unsat-core)
