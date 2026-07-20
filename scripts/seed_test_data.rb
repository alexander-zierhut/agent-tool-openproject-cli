# Idempotent test-data seed for the `op` CLI integration suite.
# Run via: ./scripts/seed_test_data.sh
#
# Ensures:
#   * newly created projects get the time/cost + wiki modules (so time logging works),
#   * two work-package custom fields exist and apply to all projects/types,
#   * a second non-admin user (jane.doe) exists for assignee/membership/report tests.

# 1. Default modules for projects created during tests.
wanted = %w[work_package_tracking costs time_tracking wiki news]
Setting.default_projects_modules = (Setting.default_projects_modules | wanted)

# Make sure the two pre-seeded projects can log time too.
Project.all.each do |p|
  p.enabled_module_names = (p.enabled_module_names | %w[costs time_tracking]).uniq
  p.save!(validate: false)
end

# 2. Work-package custom fields, available everywhere.
string_cf = WorkPackageCustomField.find_or_create_by!(name: 'Billing Ref') do |c|
  c.field_format = 'string'
  c.is_required = false
end
list_cf = WorkPackageCustomField.find_or_create_by!(name: 'Severity') do |c|
  c.field_format = 'list'
  c.is_required = false
  c.possible_values = %w[Low Medium High]
end
[string_cf, list_cf].each do |cf|
  cf.update!(is_for_all: true)
  Type.all.each { |t| t.custom_fields << cf unless t.custom_fields.include?(cf) }
end

# 2b. Make the common work-package types available in new projects (so tests
# that use Bug/Feature/Milestone don't hit "type not allowed").
Type.where(name: %w[Task Milestone Feature Bug Epic]).update_all(is_default: true)

# 2c. Time-entry custom fields (for the per-entry cost report / CSV export).
te_string = TimeEntryCustomField.find_or_create_by!(name: 'Cost Center') do |c|
  c.field_format = 'string'; c.is_required = false
end
te_bool = TimeEntryCustomField.find_or_create_by!(name: 'Billable') do |c|
  c.field_format = 'bool'; c.is_required = false
end
[te_string, te_bool].each { |cf| cf.update!(is_for_all: true) }

# 2d. Project custom fields (project attributes) — for `project get --attributes`,
# `cf project -P`, and `cost open` (which reads a billing cut-off date + a billable
# flag off the project). Values are set on the demo project so `cost open` has a
# window to sum; the cut-off is far in the past so every logged entry counts.
#
# Best-effort + wrapped: newer OpenProject models project attributes with a
# required ProjectCustomFieldSection and per-project enablement, older ones use
# is_for_all. If a given version won't take this, we warn and continue so the
# rest of the seed (tokens, users, WP fields) still succeeds — the project-
# attribute integration tests then skip rather than the whole suite failing.
$proj_cf_ok = "proj_cf=unavailable"
begin
  section = ProjectCustomFieldSection.find_or_create_by!(name: 'Billing') if defined?(ProjectCustomFieldSection)
  mk = lambda do |name, fmt, **opts|
    ProjectCustomField.find_or_create_by!(name: name) do |c|
      c.field_format = fmt
      c.is_required = false
      c.custom_field_section = section if section && c.respond_to?(:custom_field_section=)
      opts.each { |k, v| c.public_send("#{k}=", v) }
    end
  end
  proj_date_cf = mk.call('Billed through', 'date')
  proj_bool_cf = mk.call('Billable', 'bool')
  proj_list_cf = mk.call('Billing Plan', 'list', possible_values: %w[Monthly Quarterly Yearly])
  cfs = [proj_date_cf, proj_bool_cf, proj_list_cf]
  cfs.each { |cf| cf.update!(is_for_all: true) }

  demo = Project.find_by(identifier: 'demo-project')
  # A second billable project with NO cut-off date, so `cost open` (sweep) reports
  # it under "skipped" (billable but nothing to compute from).
  scrum = Project.find_by(identifier: 'your-scrum-project')

  # Enable the attributes on the seeded projects for the sectioned model (no-op
  # where is_for_all already covers it).
  if defined?(ProjectCustomFieldProjectMapping)
    [demo, scrum].compact.each do |p|
      cfs.each { |cf| ProjectCustomFieldProjectMapping.find_or_create_by!(project_id: p.id, custom_field_id: cf.id) }
    end
  end

  if demo
    quarterly = proj_list_cf.custom_options.find_by(value: 'Quarterly')
    demo.custom_field_values = {
      proj_date_cf.id => '2020-01-01',
      proj_bool_cf.id => true,
      proj_list_cf.id => quarterly&.id,
    }
    demo.save!(validate: false)
  end
  if scrum
    scrum.custom_field_values = { proj_bool_cf.id => true }
    scrum.save!(validate: false)
  end
  $proj_cf_ok = "proj_date_cf=customField#{proj_date_cf.id} proj_bool_cf=customField#{proj_bool_cf.id} " \
                "proj_list_cf=customField#{proj_list_cf.id}"
rescue => e
  warn "SEED_WARN project custom fields not seeded (#{e.class}: #{e.message})"
end

# 3. Second user.
jane = User.find_by(login: 'jane.doe')
unless jane
  jane = User.new(login: 'jane.doe', firstname: 'Jane', lastname: 'Doe',
                  mail: 'jane@example.net', admin: false)
  jane.password = 'JanePass123!'
  jane.password_confirmation = 'JanePass123!'
  jane.status = :active
  jane.save!
end

puts "SEED_OK string_cf=customField#{string_cf.id} list_cf=customField#{list_cf.id} " \
     "list_options=#{list_cf.custom_options.pluck(:id, :value).inspect} jane=#{jane.id} " \
     "#{$proj_cf_ok}"
