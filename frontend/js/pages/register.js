import { signUp } from "/js/auth.js";
import { validateRegistration } from "/js/validation.js";

const form = document.getElementById("register-form");
const message = document.getElementById("message");
const button = form.querySelector("button[type=submit]");

function show(text, type) {
  message.textContent = text;
  message.className = `message ${type}`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  message.textContent = "";
  message.className = "message";

  const values = {
    firstName: document.getElementById("first-name").value.trim(),
    lastName: document.getElementById("last-name").value.trim(),
    email: document.getElementById("email").value.trim(),
    phone: document.getElementById("phone").value.trim(),
    password: document.getElementById("password").value,
    confirmPassword: document.getElementById("confirm-password").value,
  };

  const problem = validateRegistration(values);
  if (problem) {
    show(problem, "error");
    return;
  }

  button.disabled = true;
  const { data, error } = await signUp(values);

  if (error) {
    console.error("Sign up failed:", error.message);
    show("We couldn't create your account. Please try again.", "error");
    button.disabled = false;
    return;
  }

  if (data.session) {
    window.location.href = "/pages/home.html";
  } else {
    // Happens when Confirm email is switched on in Supabase
    show("Check your email to confirm your account, then log in.", "success");
  }
});