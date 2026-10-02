import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";
import { PrismaAdapter } from "@auth/prisma-adapter";
import { db } from "@/lib/db";
import { emailAllowed } from "@/lib/allowed-email";

// Dev-login is a local convenience (and what the E2E suite uses). It can never be on in production.
export const devLoginEnabled = process.env.AUTH_DEV_LOGIN === "1" && process.env.NODE_ENV !== "production";

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: PrismaAdapter(db),
  session: { strategy: "jwt" },
  trustHost: true,
  pages: { signIn: "/" },
  providers: [
    Google,
    ...(devLoginEnabled
      ? [
          Credentials({
            id: "dev",
            name: "Dev login",
            credentials: { email: {} },
            async authorize(creds) {
              const email = String(creds?.email ?? "").trim().toLowerCase();
              if (!email.includes("@")) return null;
              return db.user.upsert({ where: { email }, update: {}, create: { email, name: email.split("@")[0] } });
            },
          }),
        ]
      : []),
  ],
  callbacks: {
    signIn: ({ user }) => emailAllowed(user.email, process.env.ALLOWED_EMAIL_DOMAINS),
    jwt: ({ token, user }) => {
      if (user?.id) token.uid = user.id;
      return token;
    },
    session: ({ session, token }) => {
      if (token.uid) session.user.id = token.uid as string;
      return session;
    },
  },
});
