import { NavLink, Route, Routes } from "react-router-dom";
import ConfigPage from "./pages/ConfigPage";
import TestChatPage from "./pages/TestChatPage";

const App = () => {
  return (
    <div className="app-shell">
      <header className="top-bar">
        <h1>oai2ant Admin</h1>
        <nav>
          <NavLink to="/" end>
            Configuration
          </NavLink>
          <NavLink to="/test">
            Test Chat
          </NavLink>
        </nav>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<ConfigPage />} />
          <Route path="/test" element={<TestChatPage />} />
        </Routes>
      </main>
    </div>
  );
};

export default App;
