import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"
import { NextResponse } from "next/server"
import { getUserRole, isSupplierRole } from "@app/auth"

const isPublicRoute = createRouteMatcher(["/sign-in(.*)"])
// Reachable only when signed in, and deliberately NOT in isPublicRoute: this is
// where the role guard below sends people, so it has to sit outside that guard
// or it redirects to itself until the browser gives up.
const isUnauthorizedRoute = createRouteMatcher(["/unauthorized"])

export default clerkMiddleware(async (auth, req) => {
  // `/` is an alias for `/home`, and the redirect has to happen here rather
  // than in an `app/page.tsx` calling redirect(). A page-level redirect reaches
  // a client-side navigation as a flight-stream error, not an HTTP redirect,
  // and the App Router deadlocks on one during the transition that follows
  // Clerk's setActive() — blank page, URL stuck on `/`, recoverable only by a
  // manual reload. Redirecting before auth.protect() also keeps `/` out of the
  // ?redirect_url= that a bounced visitor carries into sign-in, so they come
  // back to `/home` directly instead of through `/`.
  if (req.nextUrl.pathname === "/") {
    return NextResponse.redirect(new URL("/home", req.url))
  }

  // Sign-in is the only public route: sign-up is invitation-only, on Clerk's Account Portal
  if (isPublicRoute(req)) return

  // Enforce authentication
  await auth.protect()

  // Enforce supplier-portal access: supplier role only.
  // orgRole is null if the user has no active org (e.g. mid-invitation flow).
  const { orgRole } = await auth()
  const role = getUserRole(orgRole)

  // The role guard's own destination, so it has to sit outside that guard or it
  // redirects to itself until the browser gives up. Someone who *does* have
  // access has no business here: send them home rather than telling them they
  // lack a permission they hold.
  if (isUnauthorizedRoute(req)) {
    if (isSupplierRole(role)) {
      return NextResponse.redirect(new URL("/home", req.url))
    }
    return
  }

  if (!isSupplierRole(role)) {
    return NextResponse.redirect(new URL("/unauthorized", req.url))
  }
})

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
}
