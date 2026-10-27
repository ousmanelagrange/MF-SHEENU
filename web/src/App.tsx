// Application web : fournisseurs (thème, famille, Refine) et table des routes.

import { Authenticated, Refine } from "@refinedev/core";
import routerProvider from "@refinedev/react-router";
import { App as AntApp, ConfigProvider } from "antd";
import frFR from "antd/locale/fr_FR";
import dayjs from "dayjs";
import "dayjs/locale/fr";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router";
import { AppShell } from "./components/AppShell";
import { FamilyProvider } from "./lib/family";
import { AuditPage } from "./features/audit/AuditPage";
import { MembersPage } from "./features/members/MembersPage";
import { TitlesPage } from "./features/titles/TitlesPage";
import { LoginPage, RegisterPage } from "./features/auth/AuthPages";
import { FamiliesPage } from "./features/families/FamiliesPage";
import { HomePage } from "./features/home/HomePage";
import { AccountPage } from "./features/account/AccountPage";
import { JoinPage } from "./features/auth/JoinPage";
import { PlatformPage } from "./features/platform/PlatformPage";
import { JoinRequestPage } from "./features/join/JoinRequestPage";
import { KinshipPage } from "./features/kinship/KinshipPage";
import { PersonFormPage } from "./features/persons/PersonFormPage";
import { PersonPage } from "./features/persons/PersonPage";
import { PersonsPage } from "./features/persons/PersonsPage";
import { ContributionsPage } from "./features/contributions/ContributionsPage";
import { EventPage } from "./features/contributions/EventPage";
import { ScalesPage } from "./features/contributions/ScalesPage";
import { DataPage } from "./features/data/DataPage";
import { MergeJoinPage } from "./features/family-merge/MergeJoinPage";
import { ProposalsPage } from "./features/proposals/ProposalsPage";
import { AlbumPage } from "./features/memory/AlbumPage";
import { AlbumsPage } from "./features/memory/AlbumsPage";
import { NarrativePage } from "./features/memory/NarrativePage";
import { NarrativesPage } from "./features/memory/NarrativesPage";
import { TimelinePage } from "./features/memory/TimelinePage";
import { DiasporaPage } from "./features/diaspora/DiasporaPage";
import { FeedPage } from "./features/social/FeedPage";
import { ModerationPage } from "./features/social/ModerationPage";
import { TreePage } from "./features/tree/TreePage";
import { authProvider } from "./providers/authProvider";
import { dataProvider } from "./providers/dataProvider";
import { theme } from "./theme";

dayjs.locale("fr");

export default function App() {
  return (
    <BrowserRouter>
      <ConfigProvider theme={theme} locale={frFR}>
        <AntApp>
          <FamilyProvider>
            <Refine
              routerProvider={routerProvider}
              dataProvider={dataProvider}
              authProvider={authProvider}
              resources={[
                { name: "persons", list: "/personnes", show: "/personnes/:id", create: "/personnes/nouvelle", edit: "/personnes/:id/modifier" },
                { name: "titles", list: "/titres" },
                { name: "members", list: "/membres" },
                { name: "invitations" },
                { name: "audit", list: "/journal" },
              ]}
              options={{ disableTelemetry: true, syncWithLocation: false }}
            >
              <Routes>
                <Route path="/connexion" element={<LoginPage />} />
                <Route path="/inscription" element={<RegisterPage />} />
                <Route path="/rejoindre/:token" element={<JoinPage />} />
                <Route path="/rattachement/:token" element={<JoinRequestPage />} />
                <Route
                  element={
                    <Authenticated key="private" fallback={<Navigate to="/connexion" replace />}>
                      <Outlet />
                    </Authenticated>
                  }
                >
                  <Route path="/familles" element={<FamiliesPage />} />
                  <Route path="/reunir/:token" element={<MergeJoinPage />} />
                  <Route path="/compte" element={<AccountPage />} />
                  <Route path="/supervision" element={<PlatformPage />} />
                  <Route element={<AppShell />}>
                    <Route index element={<HomePage />} />
                    <Route path="/fil" element={<FeedPage />} />
                    <Route path="/moderation" element={<ModerationPage />} />
                    <Route path="/memoire" element={<NarrativesPage />} />
                    <Route path="/memoire/recits/:id" element={<NarrativePage />} />
                    <Route path="/memoire/albums" element={<AlbumsPage />} />
                    <Route path="/memoire/albums/:id" element={<AlbumPage />} />
                    <Route path="/memoire/frise" element={<TimelinePage />} />
                    <Route path="/diaspora" element={<DiasporaPage />} />
                    <Route path="/arbre" element={<TreePage />} />
                    <Route path="/personnes" element={<PersonsPage />} />
                    <Route path="/personnes/nouvelle" element={<PersonFormPage />} />
                    <Route path="/personnes/:id" element={<PersonPage />} />
                    <Route path="/personnes/:id/modifier" element={<PersonFormPage />} />
                    <Route path="/parente" element={<KinshipPage />} />
                    <Route path="/titres" element={<TitlesPage />} />
                    <Route path="/membres" element={<MembersPage />} />
                    <Route path="/journal" element={<AuditPage />} />
                    <Route path="/propositions" element={<ProposalsPage />} />
                    <Route path="/donnees" element={<DataPage />} />
                    <Route path="/cotisations" element={<ContributionsPage />} />
                    <Route path="/cotisations/baremes" element={<ScalesPage />} />
                    <Route path="/cotisations/:id" element={<EventPage />} />
                  </Route>
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Refine>
          </FamilyProvider>
        </AntApp>
      </ConfigProvider>
    </BrowserRouter>
  );
}
