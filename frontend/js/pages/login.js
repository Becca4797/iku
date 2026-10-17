import { logIn } from "/js/auth.js";
import { validateLogin } from "/js/validation.js";

const form = document.getElementById("login-form");
const message = document.getElementById("message");
const button = form.querySelector("button[type=submit]");

function showError(text) {
  message.textContent = text;
  message.className = "message error";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  message.textContent = "";
  message.className = "message";

  const values = {
    email: document.getElementById("email").value.trim(),
    password: document.getElementById("password").value,
  };

  const problem = validateLogin(values);
  if (problem) {
    showError(problem);
    return;
  }

  button.disabled = true;
  const { error } = await logIn(values);

  if (!error) {
    window.location.href = "/pages/home.html";
    return;
  }

  console.error("Login failed:", error.message);

  const badCredentials =
    error.code === "invalid_credentials" ||
    error.message.toLowerCase().includes("invalid login credentials");

  showError(
    badCredentials
      ? "Incorrect email or password."
      : "Something went wrong. Please try again."
  );
  button.disabled = false;
});