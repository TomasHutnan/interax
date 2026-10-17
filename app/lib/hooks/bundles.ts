import { mutate } from "swr";
import { Interaction, PatientForm } from "../typings";
import useSWRFetch, {
  MutationOptions,
  useSWRMutationFetch,
} from "./use-swr-fetch";

const getFormOptions: MutationOptions<string, { data: PatientForm }> = {
  toastMessages: {
    loading: "Looking up code...",
    success: "Patient form loaded.",
    error: {
      [404]: "No patient form found for this code.",
    },
  },
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
  toastMessages: {
    loading: "Loading regimen substances...",
    success: "Regimen substances loaded.",
    error: {
      [404]: "Regimen not found.",
    },
  },
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
