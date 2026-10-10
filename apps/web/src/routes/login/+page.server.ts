import { fail, redirect } from "@sveltejs/kit";
import { APIError } from "better-auth/api";

import { safeRedirectPath } from "#lib/redirect.js";
import { auth } from "#lib/server/auth.js";

import type { Actions, PageServerLoad } from "./$types";

export const load: PageServerLoad = ({ locals, url }) => {
  if (locals.user) redirect(303, safeRedirectPath(url.searchParams.get("redirectTo")));
};

export const actions: Actions = {
  default: async ({ request, url }) => {
    const form = await request.formData();
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");

    if (!email || !password) {
      return fail(400, { email, message: "Escriba su correo y su contraseña." });
    }

    try {
      await auth.api.signInEmail({ body: { email, password }, headers: request.headers });
    } catch (e) {
      if (e instanceof APIError) {
        return fail(400, { email, message: "Correo o contraseña incorrectos." });
      }
      throw e;
    }

    redirect(303, safeRedirectPath(url.searchParams.get("redirectTo")));
  },
};
