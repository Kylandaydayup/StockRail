import { api } from "./api.js";
import { readAvatarFile } from "./image-upload.js";

const form = document.querySelector("#login-form");
const registerForm = document.querySelector("#register-form");
const resetForm = document.querySelector("#reset-form");
const errorNode = document.querySelector("#login-error");
const registerErrorNode = document.querySelector("#register-error");
const resetErrorNode = document.querySelector("#reset-error");
const inviteCode = new URLSearchParams(location.search).get("invite") || "";

registerForm.elements.inviteCode.value = inviteCode;

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
    const avatarFile = data.get("avatarFile");
    await api("/api/register", {
      method: "POST",
      body: {
        email: data.get("email"),
        password: data.get("password"),
        nickname: data.get("nickname"),
        verificationCode: data.get("verificationCode"),
        inviteCode: data.get("inviteCode"),
        avatarImage: await readAvatarFile(avatarFile)
      }
    });
    location.href = "/";
  } catch (error) {
    registerErrorNode.textContent = error.message;
  }
});

document.querySelector('[data-send-code="register"]').addEventListener("click", async (event) => {
  await sendCode(event.currentTarget, registerForm, registerErrorNode, "/api/register/code");
});

document.querySelector('[data-send-code="reset"]').addEventListener("click", async (event) => {
  await sendCode(event.currentTarget, resetForm, resetErrorNode, "/api/password-reset/code");
});

resetForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetErrorNode.textContent = "";
  const data = new FormData(resetForm);
  try {
    await api("/api/password-reset", {
      method: "POST",
      body: {
        email: data.get("email"),
        password: data.get("password"),
        verificationCode: data.get("verificationCode")
      }
    });
    resetErrorNode.textContent = "密码已重置，请返回登录";
    resetForm.reset();
  } catch (error) {
    resetErrorNode.textContent = error.message;
  }
});

async function sendCode(button, targetForm, errorNode) {
  errorNode.textContent = "";
  const email = new FormData(targetForm).get("email");
  const endpoint = button.dataset.sendCode === "reset" ? "/api/password-reset/code" : "/api/register/code";
  try {
    const payload = await api(endpoint, {
      method: "POST",
      body: { email }
    });
    startCountdown(button, payload.cooldownSeconds || 60);
  } catch (error) {
    errorNode.textContent = error.message;
  }
}

function startCountdown(button, seconds) {
  let remaining = seconds;
  button.disabled = true;
  button.textContent = `${remaining}s`;
  const timer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(timer);
      button.disabled = false;
      button.textContent = "发送验证码";
      return;
    }
    button.textContent = `${remaining}s`;
  }, 1000);
}
