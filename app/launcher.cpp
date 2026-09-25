#define UNICODE
#define _UNICODE
#include <windows.h>
#include <string>
// Starts app\desktop.py with the private interpreter, without a console. Two layouts exist:
// a virtual environment (runtime\python\Scripts\pythonw.exe, a developer's clone) and the
// embeddable distribution shipped by the binary release (runtime\python\pythonw.exe).
static bool exists(const std::wstring& file) {
    DWORD attributes = GetFileAttributesW(file.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}
int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR arguments, int) {
    wchar_t path[32768]; GetModuleFileNameW(nullptr, path, 32768);
    std::wstring root(path); root.resize(root.find_last_of(L"\\/"));
    std::wstring python = root + L"\\runtime\\python\\Scripts\\pythonw.exe";
    if (!exists(python)) python = root + L"\\runtime\\python\\pythonw.exe";
    std::wstring command = L"\"" + python + L"\" \"" + root + L"\\app\\desktop.py\" " + arguments;
    STARTUPINFOW startup{}; startup.cb = sizeof(startup); PROCESS_INFORMATION process{};
    if (!CreateProcessW(python.c_str(), command.data(), nullptr, nullptr, FALSE, 0, nullptr, root.c_str(), &startup, &process)) {
        MessageBoxW(nullptr, L"Runtime manquant ou lancement impossible. Consulter LISEZ-MOI.md.", L"CyTools_MeshStudio", MB_ICONERROR); return 1;
    }
    CloseHandle(process.hThread); CloseHandle(process.hProcess); return 0;
}
