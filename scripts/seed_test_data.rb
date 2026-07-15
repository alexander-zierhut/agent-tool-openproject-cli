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
     "list_options=#{list_cf.custom_options.pluck(:id, :value).inspect} jane=#{jane.id}"
