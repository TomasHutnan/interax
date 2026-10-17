import { REGEXP_ONLY_DIGITS } from "input-otp";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSeparator,
  InputOTPSlot,
} from "../ui/input-otp";
import { Button } from "../ui/button";
import { useState, SubmitEvent } from "react";
import { useGetForm } from "@/lib/hooks/bundles";
import { useRouter } from "next/navigation";

export function OTPForm() {
  const [otp, setOTP] = useState("");
  const { trigger, isMutating } = useGetForm();
  const router = useRouter();

  function onSubmit(e: SubmitEvent) {
    e.preventDefault();
    if (otp.length < 6) return;
    trigger(otp)
      .then(() => {
        setOTP("");
        router.push(`/doctor/view?code=${otp}`);
      })
      .catch(() => {});
  }

  return (
    <form onSubmit={onSubmit} className={"flex flex-col gap-4 min-w-64"}>
      <h1 className={"text-center text-sm"}>
        Input patient PIN code to continue:
      </h1>
      <InputOTP
        maxLength={6}
        value={otp}
        onChange={(e) => setOTP(e)}
        pattern={REGEXP_ONLY_DIGITS}
      >
        <InputOTPGroup className="*:data-[slot=input-otp-slot]:h-12 *:data-[slot=input-otp-slot]:w-11 *:data-[slot=input-otp-slot]:text-xl">
          <InputOTPSlot index={0} />
          <InputOTPSlot index={1} />
          <InputOTPSlot index={2} />
        </InputOTPGroup>
        <InputOTPSeparator />
        <InputOTPGroup className="*:data-[slot=input-otp-slot]:h-12 *:data-[slot=input-otp-slot]:w-11 *:data-[slot=input-otp-slot]:text-xl">
          <InputOTPSlot index={3} />
          <InputOTPSlot index={4} />
          <InputOTPSlot index={5} />
        </InputOTPGroup>
      </InputOTP>
      <div className="flex justify-center">
        <Button
          className={"min-w-1/3"}
          type={"submit"}
          disabled={otp.length < 6 || isMutating}
        >
          {isMutating ? "Checking..." : "Continue"}
        </Button>
      </div>
    </form>
  );
}
