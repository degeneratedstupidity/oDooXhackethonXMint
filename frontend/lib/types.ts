export type EmployeeProfile = {
  job_position: string;
  department: string;
  manager: number | null;
  manager_name: string;
  location: string;
  date_of_birth: string | null;
  residing_address: string;
  nationality: string;
  personal_email: string;
  gender: string;
  marital_status: string;
  about: string;
  what_i_love_about_my_job: string;
  interests_and_hobbies: string;
  skills: string[];
  certifications: string[];
};

export type BankDetail = {
  bank_name: string;
  account_number: string;
  ifsc_code: string;
  pan_number: string;
  uan_number: string;
};

export type EmployeeDetail = {
  id: number;
  login_id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  role: "admin" | "hr_officer" | "employee";
  avatar: string | null;
  date_of_joining: string;
  company_name: string;
  profile: EmployeeProfile;
  bank_detail: BankDetail;
};

export type SalaryComponent = {
  id: number;
  code: string;
  label: string;
  computation_type: string;
  value: string;
  amount: string;
};

export type SalaryStructure = {
  id: number;
  user: number;
  employee_name: string;
  monthly_wage: string;
  yearly_wage: string;
  working_days_per_week: number;
  break_time_hours: string;
  pf_employee_percent: string;
  pf_employer_percent: string;
  professional_tax: string;
  pf_employee_amount: string;
  pf_employer_amount: string;
  components: SalaryComponent[];
};
