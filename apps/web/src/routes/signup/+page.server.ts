import { fail, redirect } from "@sveltejs/kit";
import { APIError } from "better-auth/api";

import { safeRedirectPath } from "#lib/redirect.js";
import { auth } from "#lib/server/auth.js";

import type { Actions, PageServerLoad } from "./$types";

export const load: PageServerLoad = ({ locals, url }) => {
  if (locals.user) redirect(303, safeRedirectPath(url.searchParams.get("redirectTo")));
};

function signUpMessage(error: APIError): { message: string; existing: boolean } {
  const code = String(error.body?.code ?? "");
  if (code.startsWith("USER_ALREADY_EXISTS")) {
    return { message: "Ya existe una cuenta con ese correo.", existing: true };
  }
  if (code === "VALIDATION_ERROR") {
    return { message: "Revise el correo: no parece válido.", existing: false };
  }
  return { message: "No se pudo crear la cuenta. Intente de nuevo.", existing: false };
}

export const actions: Actions = {
  default: async ({ request, url }) => {
    const form = await request.formData();
    const name = String(form.get("name") ?? "").trim();
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");

    if (!name || !email) {
      return fail(400, { name, email, message: "Escriba su nombre y su correo.", existing: false });
    }
    if (password.length < 8) {
      return fail(400, {
        name,
        email,
        message: "La contraseña necesita al menos 8 caracteres.",
        existing: false,
      });
    }

    try {
      await auth.api.signUpEmail({ body: { name, email, password }, headers: request.headers });
    } catch (e) {
      if (e instanceof APIError) return fail(400, { name, email, ...signUpMessage(e) });
      throw e;
    }

    redirect(303, safeRedirectPath(url.searchParams.get("redirectTo")));
  },
};
