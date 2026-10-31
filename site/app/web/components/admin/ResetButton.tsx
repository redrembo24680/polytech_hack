"use client";

import { useState } from "react";
import { mutate } from "swr";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

export function ResetButton() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  async function reset() {
    setBusy(true);
    try {
      await api.post("/api/admin/reset");
      await mutate(() => true);
      toast.success("Демо-дані скинуто");
      setOpen(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Не вдалося скинути демо");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="secondary" size="sm" className="w-full" onClick={() => setOpen(true)}>
        Скинути демо
      </Button>
      <Modal
        open={open}
        onClose={() => !busy && setOpen(false)}
        title="Скинути демо?"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>Ні</Button>
            <Button variant="danger" loading={busy} onClick={reset}>Скинути</Button>
          </>
        }
      >
        <p className="text-sm text-slate-700">
          Усі дані (бронювання, клієнти, тікети, чати) повернуться до початкового стану.
        </p>
      </Modal>
    </>
  );
}
