export function validatePassword(password) {
  if (password.length < 8) return "Password must be at least 8 characters.";
  if (!/[A-Za-z]/.test(password)) return "Password must contain letters.";
  if (!/[0-9]/.test(password)) return "Password must contain numbers.";
  return null;
}

function validEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// Each function returns an error message, or null if everything is fine
export function validateRegistration({ firstName, lastName, email, phone, password, confirmPassword }) {
  if (!firstName || !lastName) return "Please enter your first and last name.";
  if (!validEmail(email)) return "Please enter a valid email address.";
  if (phone && !/^[0-9+()\-\s]{6,20}$/.test(phone)) return "Please enter a valid phone number.";
  const passwordProblem = validatePassword(password);
  if (passwordProblem) return passwordProblem;
  if (password !== confirmPassword) return "Passwords do not match.";
  return null;
}

export function validateLogin({ email, password }) {
  if (!validEmail(email)) return "Please enter a valid email address.";
  if (!password) return "Please enter your password.";
  return null;
}