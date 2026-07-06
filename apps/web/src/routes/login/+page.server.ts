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
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");

    if (!email || !password) {
      return fail(400, { email, message: "Complete el correo y la contraseña." });
    }

    try {
      await auth.api.signInEmail({ body: { email, password }, headers: request.headers });
    } catch (e) {
      if (e instanceof APIError) {
        return fail(400, { email, message: "Credenciales inválidas." });
      }
      throw e;
    }

    redirect(303, "/dashboard");
  },
};
