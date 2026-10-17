import { signUp } from "/js/auth.js";
import { validateRegistration } from "/js/validation.js";

const form = document.getElementById("register-form");
const message = document.getElementById("message");
const button = form.querySelector("button[type=submit]");

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

  // Mistakes on the form are shown on the page so the user can fix them
  const problem = validateRegistration(values);
  if (problem) {
    message.textContent = problem;
    message.classList.add("error");
    return;
  }

  button.disabled = true;
  const { error } = await signUp(values);

  if (error) {
    console.error("Sign up failed:", error.message);
    window.location.href = "/pages/test.html?result=failed";
    return;
  }
  window.location.href = "/pages/test.html?result=success";
});