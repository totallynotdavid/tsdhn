import { fail, redirect } from "@sveltejs/kit";
import { APIError } from "better-auth/api";

import { auth } from "$lib/server/auth";

import type { Actions, PageServerLoad } from "./$types";

export const load: PageServerLoad = ({ locals }) => {
  if (locals.user) redirect(303, "/dashboard");
};

export const actions: Actions = {
  default: async ({ request }) => {
    const form = await request.formData();
    const name = String(form.get("name") ?? "");
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");

    if (!name || !email || password.length < 8) {
      return fail(400, {
        name,
        email,
        message: "Nombre, correo y una contraseña de al menos 8 caracteres.",
      });
    }

    try {
      await auth.api.signUpEmail({
        body: { name, email, password },
        headers: request.headers,
      });
    } catch (e) {
      if (e instanceof APIError) {
        return fail(400, { name, email, message: "No se pudo crear la cuenta." });
      }
      throw e;
    }

    redirect(303, "/dashboard");
  },
};
