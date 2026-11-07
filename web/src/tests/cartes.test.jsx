import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ExportCartes, { PdfCartesConnues } from "../admin/ExportCartes.jsx";

/** fetch simulé qui renvoie un PDF ; garde les corps envoyés. */
function fauxPdf(status = 200, detail = null) {
  const appels = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url, { method, body }) => {
      appels.push({ cle: `${method} ${url.replace(/^\/api/, "")}`, corps: JSON.parse(body) });
      return { ok: status < 400, status, blob: async () => new Blob(["%PDF"]), json: async () => ({ detail }) };
    }),
  );
  vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  return appels;
}

describe("cartes d'accès en PDF (ticket #23)", () => {
  it("exige la confirmation avant de réémettre les codes de la sélection", async () => {
    const appels = fauxPdf();
    const onExporte = vi.fn();
    render(<ExportCartes jeton="j" ids={[3, 4]} classes={[]} onFermer={() => {}} onExporte={onExporte} />);

    const bouton = screen.getByRole("button", { name: /Télécharger le PDF/ });
    expect(screen.getByLabelText(/Les 2 élève\(s\) sélectionné\(s\)/)).toBeChecked();
    expect(bouton).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText(/Cartes par feuille/), "6");
    await userEvent.click(screen.getByLabelText(/J'ai compris/));
    await userEvent.click(bouton);

    expect(appels).toEqual([
      {
        cle: "POST /admin/cartes/pdf",
        corps: { ids: [3, 4], par_page: 6, nouveaux_codes: true, origine: window.location.origin },
      },
    ]);
    expect(onExporte).toHaveBeenCalled();
  });

  it("exporte tout un niveau, et affiche l'erreur de l'API", async () => {
    const appels = fauxPdf(422, "Aucun élève à exporter.");
    render(<ExportCartes jeton="j" classes={[]} onFermer={() => {}} />);
    await userEvent.selectOptions(screen.getByLabelText("Niveau"), "3e");
    await userEvent.click(screen.getByLabelText(/J'ai compris/));
    await userEvent.click(screen.getByRole("button", { name: /Télécharger le PDF/ }));
    expect(appels[0].corps).toMatchObject({ niveau: "3e", par_page: 8 });
    expect(await screen.findByText("Aucun élève à exporter.")).toBeInTheDocument();
  });

  it("après un import, imprime les cartes connues sans nouveau code", async () => {
    const appels = fauxPdf();
    render(<PdfCartesConnues jeton="j" cartes={[{ id: 9, code: "ABCD-EFGH", prenom: "Inès" }]} />);
    await userEvent.click(screen.getByRole("button", { name: /Cartes en PDF A4 \(1\)/ }));
    expect(appels).toEqual([
      {
        cle: "POST /admin/cartes/pdf/connues",
        corps: { cartes: [{ id: 9, code: "ABCD-EFGH" }], par_page: 8, origine: window.location.origin },
      },
    ]);
  });
});
