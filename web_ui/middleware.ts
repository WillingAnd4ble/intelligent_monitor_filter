import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const matcher = ["/dashboard", "/library", "/terminal", "/feed"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!matcher.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }

  const cookieName = process.env.AUTH_SESSION_COOKIE_NAME;
  if (!cookieName) {
    return NextResponse.next();
  }

  if (!request.cookies.get(cookieName)?.value) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard", "/library", "/terminal", "/feed"],
};
