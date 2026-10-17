"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { KeyRound, Pencil, Plus, Trash2, Undo2 } from "lucide-react";
import { useForms, useUploads } from "@/lib/hooks/use-forms";
import { useNow } from "@/lib/hooks/use-now";
import { getErrorMessage } from "@/lib/hooks/use-swr-fetch";
import { deleteForm, deleteUpload, saveUpload, Upload } from "@/lib/storage";
import {
  formatRemaining,
  isActive,
  remainingMs,
  revokeUpload,
  uploadForm,
} from "@/lib/uploads";
import { PatientForm } from "@/lib/typings";
import { Button } from "../ui/button";
import { Spinner } from "../ui/spinner";
import { toast } from "../ui/toast";

export default function PatientFormList() {
  const t = useTranslations("patient.list");
  const router = useRouter();
  const forms = useForms();
  const uploads = useUploads();
  const [busy, setBusy] = useState(false);
  const ids = useMemo(
    () =>
      forms ? Object.keys(forms).sort((a, b) => Number(b) - Number(a)) : [],
    [forms],
  );
  const now = useNow(!!uploads && Object.keys(uploads).length > 0);

  // forget expired uploads, which also stops the countdown
  useEffect(() => {
    if (!uploads || !now) return;
    for (const [id, upload] of Object.entries(uploads)) {
      if (!isActive(upload, now)) deleteUpload(id);
    }
  }, [uploads, now]);

  if (!forms || !uploads || !now)
    return (
      <div className={"flex flex-1 items-center justify-center"}>
        <Spinner className={"size-8"} />
      </div>
    );

  function create() {
    router.push(`/patient/view?id=${Date.now()}`);
  }

  function remove(id: string) {
    if (!window.confirm(t("confirmDelete"))) return;

    // do not leave a valid code behind for a form that no longer exists
    const upload = uploads?.[id];
    if (isActive(upload, Date.now())) revokeUpload(upload).catch(() => {});

    if (deleteForm(id)) {
      deleteUpload(id);
      toast.add({ type: "info", title: t("toasts.deleted") });
    } else toast.add({ type: "error", title: t("toasts.deleteFailed") });
  }

  function copyCode(code: string) {
    // the clipboard is unavailable outside secure contexts
    Promise.resolve()
      .then(() => navigator.clipboard.writeText(code))
      .then(() => toast.add({ type: "success", title: t("toasts.pinCopied") }))
      .catch(() =>
        toast.add({ type: "error", title: t("toasts.pinCopyFailed") }),
      );
  }

  function getCode(id: string) {
    if (busy) return;

    setBusy(true);
    try {
      toast
        .promise(uploadForm(forms![id]), {
          loading: t("toasts.generating"),
          success: t("toasts.codeCreated"),
          error: (err) =>
            getErrorMessage(
              err instanceof Error ? err : new Error(String(err)),
            ),
        })
        .then((upload) => {
          if (!saveUpload(id, upload))
            toast.add({
              type: "warning",
              title: t("toasts.codeNotSaved"),
            });
        })
        .catch(() => {})
        .finally(() => setBusy(false));
    } catch {
      setBusy(false);
    }
  }

  function revoke(id: string, upload: Upload) {
    if (busy) return;

    setBusy(true);
    try {
      toast
        .promise(revokeUpload(upload), {
          loading: t("toasts.revoking"),
          success: t("toasts.revoked"),
          error: (err) =>
            getErrorMessage(
              err instanceof Error ? err : new Error(String(err)),
            ),
        })
        .then(() => {
          deleteUpload(id);
        })
        .catch(() => {})
        .finally(() => setBusy(false));
    } catch {
      setBusy(false);
    }
  }

  return (
    <div className={"space-y-4 border border-border surface p-4 shadow-md"}>
      <div className={"flex items-center justify-between gap-2"}>
        <h1 className={"text-base font-bold"}>{t("title")}</h1>
        <Button type={"button"} size={"lg"} onClick={create}>
          <Plus />
          {t("create")}
        </Button>
      </div>
      {ids.length === 0 && (
        <p className={"py-8 text-center text-muted-foreground"}>{t("empty")}</p>
      )}
      <ul className={"space-y-3"}>
        {ids.map((id, index) => {
          const upload = uploads[id];
          const active = isActive(upload, now);

          return (
            <li
              key={id}
              className={
                "space-y-3 border border-muted-foreground p-4 shadow-md"
              }
            >
              {active && (
                <div
                  className={
                    "-mt-4 -mx-4 flex items-center justify-between space-y-1 bg-green-500/50 px-4 py-2 text-center"
                  }
                >
                  <button
                    type={"button"}
                    className={"cursor-pointer text-left text-2xl font-bold"}
                    aria-label={t("copyPin")}
                    onClick={() => copyCode(upload.id)}
                  >
                    {t("pin", {
                      code: `${upload.id.substring(0, 3)}-${upload.id.substring(3)}`,
                    })}
                  </button>
                  <p className={"text-xs"}>
                    {t("expiresIn", {
                      time: formatRemaining(remainingMs(upload, now)),
                    })}
                  </p>
                </div>
              )}
              <FormSummary id={id} form={forms[id]} />
              <div className={"grid grid-cols-2 gap-2"}>
                <Button
                  type={"button"}
                  size={"lg"}
                  variant={"outline"}
                  onClick={() => router.push(`/patient/view?id=${id}`)}
                >
                  <Pencil />
                  {t("edit")}
                </Button>
                <Button
                  type={"button"}
                  size={"lg"}
                  variant={"destructive"}
                  onClick={() => remove(id)}
                >
                  <Trash2 />
                  {t("delete")}
                </Button>
                {active ? (
                  <Button
                    type={"button"}
                    size={"lg"}
                    variant={"outline"}
                    className={"col-span-2"}
                    disabled={busy}
                    onClick={() => revoke(id, upload)}
                  >
                    <Undo2 />
                    {t("revoke")}
                  </Button>
                ) : (
                  index === 0 && (
                    <Button
                      type={"button"}
                      size={"lg"}
                      className={"col-span-2"}
                      disabled={busy}
                      onClick={() => getCode(id)}
                    >
                      <KeyRound />
                      {t("getCode")}
                    </Button>
                  )
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function FormSummary({ id, form }: { id: string; form: PatientForm }) {
  const t = useTranslations("patient.list");
  const drugs = form.prescriptions.map((p) => p.drug.trim()).filter(Boolean);

  return (
    <div className={"space-y-1"}>
      <p className={"text-xs text-muted-foreground"}>
        {new Date(Number(id)).toLocaleString()}
      </p>
      <p className={"text-base font-bold break-words"}>
        {form.treatment.name.trim() || t("noRegimen")}
      </p>
      <p className={"break-words"}>
        {drugs.length > 0 ? drugs.join(", ") : t("noPrescriptions")}
      </p>
    </div>
  );
}
