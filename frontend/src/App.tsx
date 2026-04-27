import { Suspense } from "react";
import { BrowserRouter } from "react-router-dom";
import { AppRoutes } from "./router";
import { I18nextProvider } from "react-i18next";
import i18n from "./i18n";
import { AuthProvider } from "./contexts/auth-provider";


function App() {
  return (
    <div className="soft-neo-app">
      <I18nextProvider i18n={i18n}>
        <BrowserRouter basename={__BASE_PATH__}>
          <AuthProvider>
            <Suspense
              fallback={
                <div className="flex min-h-screen items-center justify-center text-sm text-gray-500">
                  页面加载中...
                </div>
              }
            >
              <AppRoutes />
            </Suspense>
          </AuthProvider>
        </BrowserRouter>
      </I18nextProvider>
    </div>
  );
}

export default App;
