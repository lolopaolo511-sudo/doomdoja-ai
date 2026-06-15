import "./style.css";
import { Game } from "./core/Game";

const root = document.getElementById("app");
if (!root) throw new Error("Missing #app root element");

// Boot the world.
new Game(root);
