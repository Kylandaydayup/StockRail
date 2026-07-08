import { api } from "./api.js";

const form = document.querySelector("#login-form");
const registerForm = document.querySelector("#register-form");
const errorNode = document.querySelector("#login-error");
const registerErrorNode = document.querySelector("#register-error");

document.querySelectorAll(".auth-tabs button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".auth-tabs button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.querySelectorAll(".auth-panel").forEach((panel) => {
      panel.hidden = panel.dataset.panelId !== button.dataset.panel;
    });
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorNode.textContent = "";
  const data = new FormData(form);
  try {
    const { user } = await api("/api/login", {
      method: "POST",
      body: {
        username: data.get("username"),
        password: data.get("password")
      }
    });
    location.href = user.role === "member" ? "/" : "/admin.html";
  } catch (error) {
    errorNode.textContent = error.message;
  }
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  registerErrorNode.textContent = "";
  const data = new FormData(registerForm);
  try {
    await api("/api/register", {
      method: "POST",
      body: {
        username: data.get("username"),
        password: data.get("password"),
        nickname: data.get("nickname"),
        avatarUrl: data.get("avatarUrl")
      }
    });
    location.href = "/";
  } catch (error) {
    registerErrorNode.textContent = error.message;
  }
});
