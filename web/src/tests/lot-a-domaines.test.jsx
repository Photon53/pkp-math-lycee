import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import BandeauAdmin, { avecDomaine } from "../admin/BandeauAdmin.jsx";
import EspaceAdmin from "../admin/EspaceAdmin.jsx";
import Professeurs from "../admin/Professeurs.jsx";
import TableauDeBord from "../admin/TableauDeBord.jsx";
import { DOMAINES_PAR_DEFAUT } from "../admin/Qualifications.jsx";
import { fausseApi } from "./setup.js";

const connecter = () =>
  sessionStorage.setItem("pkp.admin", JSON.stringify({ jeton: "j", nom: "Admin", expire_le: Date.now() + 600_000 }));

describe("lot A : domaine et recherche globale", () => {
  it("ajoute le domaine choisi aux appels de l'API", () => {
    expect(avecDomaine("/admin/classes", "")).toBe("/admin/classes");
    expect(avecDomaine("/admin/classes", "anglais-college")).toBe("/admin/classes?domaine=anglais-college");
    expect(avecDomaine("/admin/contenu?niveau=2nde", "maths-lycee")).toBe("/admin/contenu?niveau=2nde&domaine=maths-lycee");
  });

  it("la recherche globale ouvre la page du résultat, filtrée", async () => {
    window.history.pushState(null, "", "/admin");
    fausseApi({
      "GET /admin/recherche?q=lin&domaine=maths-lycee": {
        json: [{ type: "Élève", libelle: "Lina", detail: "2NDE-A · M. Demo", vers: "/admin/eleves?q=Lina" }],
      },
    });
    const onOuvrir = vi.fn();
    render(
      <BandeauAdmin jeton="j" onExpire={vi.fn()} domaines={DOMAINES_PAR_DEFAUT} domaine="maths-lycee" onDomaine={vi.fn()} onOuvrir={onOuvrir} />,
    );
    await userEvent.type(screen.getByLabelText("Recherche globale"), "lin");
    const resultats = await screen.findByRole("listbox", { name: "Résultats de la recherche" });
    await userEvent.click(within(resultats).getByRole("option", { name: /Lina/ }));
    expect(window.location.pathname + window.location.search).toBe("/admin/eleves?q=Lina");
    expect(onOuvrir).toHaveBeenCalled();
  });

  it("la liste de l'équipe suit le domaine choisi", async () => {
    window.history.pushState(null, "", "/admin/professeurs");
    const appels = fausseApi({
      "GET /admin/domaines": { json: DOMAINES_PAR_DEFAUT },
      "GET /admin/enseignants?domaine=anglais-college": { json: [] },
    });
    render(<Professeurs jeton="j" onExpire={vi.fn()} domaine="anglais-college" />);
    await waitFor(() => expect(appels.some((a) => a.cle === "GET /admin/enseignants?domaine=anglais-college")).toBe(true));
  });

  it("le tableau de bord dit ce qu'il couvre hors Maths lycée", () => {
    fausseApi({ "GET /admin/statistiques?periode=30": { json: null } });
    render(<TableauDeBord jeton="j" onExpire={vi.fn()} domaine="anglais-college" domaines={DOMAINES_PAR_DEFAUT} />);
    expect(screen.getByText(/couvre Maths lycée pour l'instant/)).toHaveTextContent("Anglais collège");
  });

  it("n'affiche que les espaces permis au compte et mémorise le domaine choisi", async () => {
    connecter();
    fausseApi({
      "GET /admin/moi": { json: { permissions: ["parents.gerer", "pilotage.global"] } },
      "GET /admin/domaines": { json: DOMAINES_PAR_DEFAUT },
      "GET /admin/statistiques?periode=30": { json: null },
    });
    render(<EspaceAdmin chemin="/admin" />);
    const navigation = screen.getByRole("navigation", { name: "Navigation Administration" });
    expect(await within(navigation).findByRole("link", { name: /Familles/ })).toBeInTheDocument();
    expect(within(navigation).queryByRole("link", { name: /Équipe/ })).not.toBeInTheDocument();
    expect(within(navigation).queryByRole("link", { name: /Domaines/ })).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Domaine"), "anglais-college");
    expect(JSON.parse(sessionStorage.getItem("pkp.admin.domaine"))).toBe("anglais-college");
  });
});
