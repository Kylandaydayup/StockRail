import { api } from "./api.js";

const form = document.querySelector("#login-form");
const errorNode = document.querySelector("#login-error");

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
