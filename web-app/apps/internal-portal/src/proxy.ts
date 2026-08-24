import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"
import { NextResponse } from "next/server"
import { getUserRole, isInternalRole } from "@rilevio/auth"

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"])

export default clerkMiddleware(async (auth, req) => {
  // Allow public routes (sign-in, sign-up) without auth
  if (isPublicRoute(req)) return

  // Enforce authentication
  await auth.protect()

  // Enforce internal-portal access: project_manager, reviewer, or approver only.
  // orgRole is null if the user has no active org (e.g. mid-invitation flow).
  const { orgRole } = await auth()
  const role = getUserRole(orgRole)

  if (!role || !isInternalRole(role)) {
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
