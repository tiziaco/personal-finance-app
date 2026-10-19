import { SignUp } from "@clerk/nextjs"
import { AuthLockup } from "@/components/layout/auth-lockup"

export default function SignUpPage() {
  return (
    <AuthLockup>
      <SignUp />
    </AuthLockup>
  )
}
