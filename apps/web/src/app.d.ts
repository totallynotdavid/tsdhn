import type { User, Session } from "better-auth";

declare global {
  namespace App {
    interface Locals {
      user?: User;
      session?: Session;
    }
  }
}

export {};
