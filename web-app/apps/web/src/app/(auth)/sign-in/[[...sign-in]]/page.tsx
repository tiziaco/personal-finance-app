import { SignIn } from "@clerk/nextjs"
import { AuthLockup } from "@/components/layout/auth-lockup"

export default function SignInPage() {
  return (
    <AuthLockup>
      <SignIn />
    </AuthLockup>
  )
}
