#!/usr/bin/env python3
"""Faux « gcloud » pour le banc de scripts/controle-acces-sauvegardes.sh (ticket #65).

Le scénario est lu dans le fichier JSON désigné par FAUX_GCLOUD_SCENARIO :
  bucket            "apres" (politique actuelle, PR 3a) | "avant" (liaisons historiques)
  troubleshooter    true si l'API Policy Troubleshooter est activée
  ts_contredit      liste de "email|permission|ressource" pour lesquels Troubleshooter inverse le résultat
  ts_erreur         idem : Troubleshooter échoue
  ts_inconnu        idem : Troubleshooter répond UNKNOWN_CONDITIONAL
  ancetres          liste de {"type": "organization"|"folder", "id": …, "autorisations": [...], "refus": [...]
                    ou "refus_illisible": true}
  groupe_bucket     true : ajoute une liaison objectViewer à un groupe sur le bucket
  sans_liste_tf     true : iam.securityReviewer sans storage.objects.list (droits réduits, option B)
  tf_lecteur_projet true : tf-plan reçoit roles/storage.objectViewer au niveau du projet (lecture du contenu)
  ts_style          "v3" (overallAccessState, défaut) | "v1" (access : GRANTED / NOT_GRANTED) | "sans_etat" (JSON
                    sans champ d'accès) | "texte" (réponse non JSON) | "valeur_inconnue" (état NOUVEL_ETAT)
                    | "fuite_jeton" (v3, mais un jeton apparaît dans la sortie et les erreurs)
                    | "v1_reel" (structure de la réponse réelle du 13/11 : access, errors, explainedPolicies,
                      adresses en noms de clés et en membres)
Chaque appel est ajouté à FAUX_GCLOUD_JOURNAL.
"""
import json
import os
import sys

P = "mer-boussole-dev"; NUM = "948330391026"; B = f"{P}-deploiement"; O = f"projects/_/buckets/{B}/objects/"
VM = f"boussole-dev-vm@{P}.iam.gserviceaccount.com"; DEP = f"boussole-dev-deployer@{P}.iam.gserviceaccount.com"
TF = f"boussole-dev-tf-plan@{P}.iam.gserviceaccount.com"; CE = f"{NUM}-compute@developer.gserviceaccount.com"

sc = json.load(open(os.environ["FAUX_GCLOUD_SCENARIO"]))
args = sys.argv[1:]
cmd = " ".join(args)
with open(os.environ["FAUX_GCLOUD_JOURNAL"], "a") as j:
    j.write(cmd + "\n")

conditionnelles = [
    {"condition": {"expression": f'resource.name.startsWith("{O}backups/")', "title": "backups-ecriture"}, "members": [f"serviceAccount:{VM}"], "role": "roles/storage.objectCreator"},
    {"condition": {"expression": f'resource.name.startsWith("{O}releases/")', "title": "releases-seulement"}, "members": [f"serviceAccount:{DEP}"], "role": "roles/storage.objectUser"},
    {"condition": {"expression": f'resource.name.startsWith("{O}releases/") || resource.name.startsWith("{O}backups/")', "title": "releases-et-backups-lecture"}, "members": [f"serviceAccount:{VM}"], "role": "roles/storage.objectViewer"},
]
if sc.get("bucket", "apres") == "apres":
    bucket = [{"members": [f"serviceAccount:{TF}"], "role": "roles/storage.bucketViewer"},
              {"members": [f"projectOwner:{P}"], "role": "roles/storage.legacyBucketOwner"}] + conditionnelles
else:
    bucket = [{"members": [f"projectEditor:{P}", f"projectOwner:{P}"], "role": "roles/storage.legacyBucketOwner"},
              {"members": [f"projectViewer:{P}"], "role": "roles/storage.legacyBucketReader"},
              {"members": [f"projectEditor:{P}", f"projectOwner:{P}"], "role": "roles/storage.legacyObjectOwner"},
              {"members": [f"projectViewer:{P}"], "role": "roles/storage.legacyObjectReader"}] + conditionnelles
if sc.get("groupe_bucket"):
    bucket.append({"members": ["group:equipe@example.invalid"], "role": "roles/storage.objectViewer"})
projet = [{"role": "roles/editor", "members": [f"serviceAccount:{CE}"]}, {"role": "roles/owner", "members": ["user:proprietaire@example.invalid"]},
          {"role": "roles/viewer", "members": [f"serviceAccount:{TF}"]}, {"role": "roles/iam.securityReviewer", "members": [f"serviceAccount:{TF}"]},
          {"role": "roles/browser", "members": [f"serviceAccount:{TF}"]}]
PERMS = {
    "roles/viewer": ["storage.buckets.list"], "roles/editor": ["storage.buckets.create", "storage.buckets.list"],
    "roles/owner": ["storage.buckets.create", "storage.buckets.list"], "roles/browser": [],
    # Permissions storage.* réelles de roles/iam.securityReviewer (relevées le 13/11/2026).
    "roles/iam.securityReviewer": ["storage.anywhereCaches.list", "storage.bucketOperations.list", "storage.buckets.getIamPolicy",
                                   "storage.buckets.list", "storage.featureConfigs.list", "storage.folders.list",
                                   "storage.hmacKeys.list", "storage.managedFolders.getIamPolicy", "storage.managedFolders.list",
                                   "storage.multipartUploads.list", "storage.objects.getIamPolicy", "storage.objects.list"],
    "roles/storage.bucketViewer": ["storage.buckets.get", "storage.buckets.list"],
    "roles/storage.legacyBucketOwner": ["storage.buckets.get", "storage.buckets.update", "storage.buckets.getIamPolicy", "storage.buckets.setIamPolicy", "storage.objects.list", "storage.objects.create", "storage.objects.delete"],
    "roles/storage.legacyBucketReader": ["storage.buckets.get", "storage.objects.list"],
    "roles/storage.legacyObjectOwner": ["storage.objects.get", "storage.objects.update"],
    "roles/storage.legacyObjectReader": ["storage.objects.get"],
    "roles/storage.objectCreator": ["storage.objects.create"],
    "roles/storage.objectUser": ["storage.objects.create", "storage.objects.delete", "storage.objects.get", "storage.objects.list", "storage.objects.update"],
    "roles/storage.objectViewer": ["storage.objects.get", "storage.objects.list"],
}
if sc.get("sans_liste_tf"):
    PERMS["roles/iam.securityReviewer"].remove("storage.objects.list")
if sc.get("tf_lecteur_projet"):
    projet.append({"role": "roles/storage.objectViewer", "members": [f"serviceAccount:{TF}"]})
ACCES_REELS = {  # accès réels attendus (vérité de Troubleshooter par défaut)
    (TF, "storage.buckets.get", f"projects/_/buckets/{B}"), (TF, "storage.buckets.getIamPolicy", f"projects/_/buckets/{B}"),
    (TF, "storage.objects.list", f"projects/_/buckets/{B}"),   # exception D5
    (DEP, "storage.objects.create", O + "releases/temoin.json"),
    (VM, "storage.objects.get", O + "backups/temoin"), (VM, "storage.objects.create", O + "backups/temoin"),
    (VM, "storage.objects.get", O + "releases/desired.json"),
}
ancetres = sc.get("ancetres", [])


def opt(nom):
    for a in args:
        if a.startswith(nom + "="):
            return a.split("=", 1)[1]
    return None


if cmd.startswith("services enable") or " enable " in f" {cmd} ":
    sys.exit("faux gcloud : ACTIVATION D'API INTERDITE PAR LE BANC")
if cmd.startswith("projects describe"):
    print(NUM)
elif cmd.startswith("storage buckets get-iam-policy"):
    print(json.dumps({"bindings": bucket, "etag": "CAY="}))
elif cmd.startswith("projects get-iam-policy"):
    print(json.dumps({"bindings": projet}))
elif cmd.startswith("projects get-ancestors"):
    print(json.dumps([{"id": P, "type": "project"}] + [{"id": a["id"], "type": a["type"]} for a in ancetres]))
elif cmd.startswith("organizations get-iam-policy") or cmd.startswith("resource-manager folders get-iam-policy"):
    ident = args[3] if args[0] == "resource-manager" else args[2]
    a = next(x for x in ancetres if x["id"] == ident)
    print(json.dumps({"bindings": a.get("autorisations", [])}))
elif cmd.startswith("iam policies list"):
    point = opt("--attachment-point")
    for a in ancetres:
        if point.endswith(f"%2F{a['id']}"):
            if a.get("refus_illisible"):
                sys.exit("ERROR: (gcloud.iam.policies.list) PERMISSION_DENIED")
            print(json.dumps(a.get("refus", [])))
            break
    else:
        print("[]")
elif cmd.startswith("iam roles describe"):
    print(json.dumps({"includedPermissions": PERMS[args[3]]}))
elif cmd.startswith("version"):
    print(json.dumps({"Google Cloud SDK": "999.0.0-faux", "core": "2026.11.01"}))
elif cmd.startswith("services list"):
    if sc.get("troubleshooter"):
        print("policytroubleshooter.googleapis.com")
elif cmd.startswith("policy-troubleshoot iam"):
    if not sc.get("troubleshooter"):
        sys.exit("ERROR: API [policytroubleshooter.googleapis.com] not enabled")
    cle = (opt("--principal-email"), opt("--permission"), opt("--resource-name"))
    texte = "|".join(cle)
    if texte in sc.get("ts_erreur", []):
        sys.exit("ERROR: (gcloud.policy-troubleshoot.iam) INVALID_ARGUMENT")
    if "--format=json" not in args:
        print("")   # un format d'extraction sur un champ absent donne une sortie vide (cas réel du 13/11)
        sys.exit(0)
    style = sc.get("ts_style", "v3")
    if texte in sc.get("ts_inconnu", []):
        etat = "UNKNOWN_CONDITIONAL"
    else:
        acces = cle in ACCES_REELS
        if texte in sc.get("ts_contredit", []):
            acces = not acces
        etat = ("GRANTED" if acces else "NOT_GRANTED") if style == "v1" else ("CAN_ACCESS" if acces else "CANNOT_ACCESS")
    if style == "v1_reel":
        explication = {"access": "NOT_GRANTED", "relevance": "NORMAL", "fullResourceName": f"//storage.googleapis.com/projects/_/buckets/{B}",
                       "bindingExplanations": [{"access": "NOT_GRANTED", "relevance": "NORMAL", "role": "roles/storage.bucketViewer",
                                                "rolePermission": "ROLE_PERMISSION_NOT_INCLUDED", "rolePermissionRelevance": "NORMAL",
                                                "memberships": {f"serviceAccount:{TF}": {"membership": "MEMBERSHIP_NOT_INCLUDED", "relevance": "NORMAL"}}}],
                       "policy": {"bindings": [{"members": ["user:personne@example.invalid"], "role": "roles/storage.legacyBucketOwner"}], "version": 1}}
        print(json.dumps({"access": "NOT_GRANTED",
                          "errors": [{"code": 7, "message": "Policy of user:personne@example.invalid not readable",
                                      "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
                                                   "domain": "policytroubleshooter.googleapis.com", "reason": "RAISON_DE_TEST"}]}],
                          "explainedPolicies": [explication, explication]}))
    elif style == "fuite_jeton":
        print("WARNING: Authorization: Bearer ya29.JETON-SECRET-DE-TEST", file=sys.stderr)
        print(json.dumps({"overallAccessState": etat, "debug": {"access_token": "ya29.JETON-SECRET-DE-TEST"}}))
    elif style == "texte":
        print(f"overallAccessState: {etat}")
    elif style == "valeur_inconnue":
        print(json.dumps({"overallAccessState": "NOUVEL_ETAT"}))
    elif style == "sans_etat":
        print(json.dumps({"accessTuple": {"principal": cle[0]}, "explainedPolicies": []}))
    elif style == "v1":
        print(json.dumps({"access": etat, "explainedPolicies": []}))
    else:
        print(json.dumps({"overallAccessState": etat, "accessTuple": {"principal": cle[0]}}))
else:
    sys.exit(f"faux gcloud : commande non simulée : {cmd}")
