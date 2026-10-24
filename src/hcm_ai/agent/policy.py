"""Company policy for Policy Q&A: the hackathon brief's Section 3 rules, plus the Section 2
role permissions and the Section 7 metric definitions. Single source: nothing else may restate
these rules. Static text (no per-request values) so the system prompt stays cacheable.

Tax slabs: the brief lists cumulative figures (30k, 210k, 510k); they equal the marginal rates
applied to the part of income above each threshold, which is how they are written here.
"""

POLICY_TEXT = """Company policy (the only rules you may state):
Roles: Admin = company setup, creates HR/employee logins, sees all data, finalizes payroll \
(Admin only; finalized runs locked), audit log, announcements. HR = registers employees (login \
with temporary password, changed at first sign-in), salary structures, approves attendance \
corrections and leave, drafts payroll, announcements; cannot finalize payroll, create Admins, \
change company settings or see the audit log. Employee = own check-in/out, attendance, \
corrections, leave, payslips, phone/address; cannot see others' data/salary, approve anything \
or edit own salary/role/attendance. JWT login, bcrypt passwords; every API checks role and scope.
Setup: office starts 09:00, grace 15 min (late after 09:15), half-day under 5h worked, weekend \
Sat-Sun, office location + radius (e.g. 150 m). Settings apply to new records only.
Attendance: server stamps time; one record per employee per day (second check-in = 409); absent = \
no record and no approved leave; missing_checkout = no check-out.
Leave: working days only (weekends and holidays skipped); yearly quotas annual 14, sick 8, \
casual 10, unpaid unlimited; overlap or over-balance = 422.
Employees: CSV import has a dry run (row, field, reason); checks required fields, unique \
code/email, valid email, known department, ISO date, salary > 0.
Payroll: gross = 1.5 x basic (HRA 40%, medical 10%); per-day rate = gross / working days in the \
month (one day's pay, not the whole gross); deduction = per-day rate x (absent days + unpaid \
days + 0.5 x half days); joiners/leavers prorated. Tax slab on gross x 12 \
(illustrative): up to 600k 0%; 600k-1.2M 5% of the part above 600k; 1.2M-2.4M 30k + 15% of the \
part above 1.2M; 2.4M-3.6M 210k + 25% of the part above 2.4M; over 3.6M 510k + 35% of the part \
above 3.6M. Admin finalizes; finalized runs are locked.
Dashboards (server-side, filter by date range and department): attendance rate = (present + \
late + missing_checkout + 0.5 x half_day) / (working-day records - on_leave); late % = late / \
(present + late); absenteeism = absent days / expected working days; leave utilization = \
approved days / quota; attrition = exits / average headcount x 100; payroll cost = sum of gross \
and net by month and department. Sample data has no missing_checkout/on_leave.
Comms/audit: announcements on dashboards, in-app notifications, audit log (actor, action, \
entity, before/after; cannot be edited or deleted)."""
