import { mutate } from "swr";
import { Interaction, PatientForm } from "../typings";
import useSWRFetch, {
  MutationOptions,
  useSWRMutationFetch,
} from "./use-swr-fetch";
import { tr } from "../i18n";

const getFormOptions: MutationOptions<string, { data: PatientForm }> = {
  toastMessages: () => ({
    loading: tr("toasts.form.loading"),
    success: tr("toasts.form.success"),
    error: {
      [404]: tr("toasts.form.notFound"),
    },
  }),
  onMutation: async (code, form) => {
    await mutate(`/api/uploads/${encodeURIComponent(code)}`, form, {
      populateCache: true,
    });
  },
  body: false,
};

export function useGetForm() {
  return useSWRMutationFetch<string, { data: PatientForm }>(
    "/form",
    (arg) => `/api/uploads/${arg}`,
    "GET",
    getFormOptions,
  );
}

const getComponentsOptions: MutationOptions<string, string[]> = {
  toastMessages: () => ({
    loading: tr("toasts.regimen.loading"),
    success: tr("toasts.regimen.success"),
    error: {
      [404]: tr("toasts.regimen.notFound"),
    },
  }),
  onMutation: async (name, form) => {
    await mutate(
      `/api/regimens/components?name=${encodeURIComponent(name)}`,
      form,
      { populateCache: true },
    );
  },
  body: false,
};

export function useGetComponents() {
  return useSWRMutationFetch<string, string[]>(
    "/components",
    (arg) => `/api/regimens/components?name=${encodeURIComponent(arg)}`,
    "GET",
    getComponentsOptions,
  );
}

const getInteractionsOptions: MutationOptions<
  { substances: string[] },
  Interaction[]
> = {
  body: true,
};

export function useGetInteractions() {
  return useSWRMutationFetch<{ substances: string[] }, Interaction[]>(
    "/api/interactions",
    () => `/api/interactions`,
    "POST",
    getInteractionsOptions,
  );
}

export function useForm(code: string) {
  return useSWRFetch<{ data: PatientForm }>(`/api/uploads/${code}`);
}
