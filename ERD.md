User
 ├── id
 ├── username
 ├── password_hash
 ├── role  -> manager / supervisor / visitor / telesales
 └── is_active

VisitorProfile
 ├── id
 ├── user_id -> User.id
 ├── visitor_code
 ├── full_name
 ├── default_start_lat
 ├── default_start_lon
 ├── default_capacity
 └── is_active

Store
 ├── id
 ├── store_code
 ├── store_name
 ├── region
 ├── lat
 ├── lon
 ├── grade
 ├── has_confectionery
 ├── has_oil
 ├── has_pasta
 ├── is_active
 └── notes

DailyVisitorStatus
 ├── id
 ├── visitor_id -> VisitorProfile.id
 ├── work_date
 ├── start_lat
 ├── start_lon
 ├── capacity
 └── is_active_today

DailyAssignment
 ├── id
 ├── work_date
 ├── visitor_id -> VisitorProfile.id
 ├── store_id -> Store.id
 ├── route_order
 ├── route_distance_km
 ├── assignment_status
 ├── generated_by -> User.id
 └── published_at

Visit
 ├── id
 ├── assignment_id -> DailyAssignment.id
 ├── store_id -> Store.id
 ├── visitor_id -> VisitorProfile.id
 ├── visit_date
 ├── result -> green / yellow / red
 ├── note
 ├── created_at
 └── updated_at

TelesalesFollowup
 ├── id
 ├── store_id -> Store.id
 ├── visit_id -> Visit.id
 ├── followup_date
 ├── contact_status
 ├── result
 ├── note
 ├── created_by -> User.id
 └── created_at