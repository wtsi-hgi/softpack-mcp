// Define the wizard app function before Alpine.js loads
window.wizardApp = function () {
  return {
    currentStep: 1,
    totalSteps: 5,

    // API Configuration
    apiBaseUrl: "{{API_BASE_URL}}",
    sessionId: null,

    // Session recovery state
    hasExistingSession: false,
    existingSessionData: null,
    showSessionChoice: false,

    // Notification system
    notifications: [],
    notificationId: 0,

    // Notification helpers
    addNotification(type, message, durationSeconds = 3) {
      const id = ++this.notificationId;
      this.notifications.push({ id, type, message });
      if (durationSeconds && durationSeconds > 0) {
        setTimeout(() => {
          this.removeNotification(id);
        }, durationSeconds * 1000);
      }
      return id;
    },

    removeNotification(id) {
      this.notifications = this.notifications.filter((n) => n.id !== id);
    },

    showError(message) {
      this.addNotification('error', message);
    },

    showSuccess(message) {
      this.addNotification('success', message);
    },

    showInfo(message) {
      this.addNotification('info', message);
    },

    // Internal flag to avoid infinite API base fallback loops
    _apiBaseUrlRetried: false,

    normalizeBaseUrl(url) {
      if (!url) return '';
      return url.replace(/\/$/, '');
    },

    ensureApiBaseUrlConfigured() {
      const isPlaceholder = typeof this.apiBaseUrl === 'string' && this.apiBaseUrl.includes('API_BASE_URL');
      if (this.apiBaseUrl && !isPlaceholder) {
        this.apiBaseUrl = this.normalizeBaseUrl(this.apiBaseUrl);
        return;
      }

      // 1) Global override (if server injected it inline or elsewhere)
      if (typeof window !== 'undefined' && window.__API_BASE_URL) {
        this.apiBaseUrl = this.normalizeBaseUrl(window.__API_BASE_URL);
        return;
      }

      // 2) Meta tag fallback
      try {
        const meta = document.querySelector('meta[name="api-base-url"]');
        if (meta && meta.content && !meta.content.includes('API_BASE_URL')) {
          this.apiBaseUrl = this.normalizeBaseUrl(meta.content);
          return;
        }
      } catch (_) {}

      // 3) Sensible default based on host (common dev setup: backend on :8000)
      const protocol = window?.location?.protocol || 'http:';
      const hostname = window?.location?.hostname || 'localhost';
      this.apiBaseUrl = `${protocol}//${hostname}:8000`;
    },

    // Package info
    packageName: "",
    pypiName: "", // Store original name for PyPI
    packageType: "",

    // Validation state
    validationCompleted: false,

    // Installation options
    installVersion: "",
    skipInstallValidation: false,

    // Workflow state
    recipeExists: "",
    recipeChecking: false,
    needsSpecificVersion: "",
    newVersion: "",
    pypiSuccess: "",
    foundInOfficial: "",
    officialChecking: false,
    hasReleases: "",
    releaseUrl: "",
    repoUrl: "",
    buildSuccess: "",
    validationSuccess: "",

    customValidationScript: "",
    hashSelection: "",
    prUrl: "",

    // API operation states
    apiStates: {
      creatingSession: false,
      runningVersions: false,
      runningChecksum: false,
      creatingPypi: false,
      copyingPackage: false,
      creatingFromUrl: false,
      creatingBlankRecipe: false,
      installingPackage: false,
      validatingPackage: false,
      uninstallingPackage: false,
      gettingCommitInfo: false,
      creatingPR: false,
      loadingRecipes: false,
      creatingRecipe: false,
      savingRecipe: false,
      validatingRecipe: false,
      requestingAccess: false,
      checkingPypi: false,
      autoCreatingRecipe: false,
    },
    step1ValidationAttempted: false,

    // Recipe editor state
    selectedRecipe: null,
    recipeContent: "",
    validationResult: null,
    aceEditor: null,
    editorCursorInfo: { row: 1, column: 1, lines: 0 },

    // Installation output state
    installOutput: [],

    // Validation output state
    validationOutput: [],

    // UI state
    showDetailedLog: false,

    // API results
    apiResults: {
      sessionInfo: null,
      versions: null,
      checksums: null,
      pypiResult: null,
      copyResult: null,
      urlResult: null,
      blankRecipeResult: null,
      installResult: null,
      validationResult: null,
      uninstallResult: null,
      commitInfo: null,
      prResult: null,
      recipes: null,
      recipeCreateResult: null,
      accessRequestResult: null,
    },

    // Modifications
    modifications: {
      dependencies: false,
      optional: false,
      patches: false,
      buildFlags: false,
      classType: false,
    },

    // Collaborator access
    hasCollaboratorAccess: "",
    githubUsername: "",

    // Cookie management functions
    setCookie(name, value, days = 7) {
      const expires = new Date();
      expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);

      // Compress the data using a simple compression technique
      const jsonString = JSON.stringify(value);
      const compressed = this.compressData(jsonString);

      // Check if the compressed data is still too large (max 3500 bytes to be safe)
      if (compressed.length > 3500) {
        console.warn(`Cookie ${name} would be too large (${compressed.length} bytes), storing minimal data instead`);
        // Store only essential data
        const minimalData = this.createMinimalSessionData(value);
        const minimalJson = JSON.stringify(minimalData);
        const minimalCompressed = this.compressData(minimalJson);

        if (minimalCompressed.length > 3500) {
          console.warn(`Even minimal session data is too large, skipping cookie storage`);
          return;
        }

        document.cookie = `${name}=${minimalCompressed};expires=${expires.toUTCString()};path=/`;
      } else {
        document.cookie = `${name}=${compressed};expires=${expires.toUTCString()};path=/`;
      }
    },

    getCookie(name) {
      const nameEQ = name + "=";
      const ca = document.cookie.split(";");
      for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === " ") c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) {
          try {
            const compressedData = c.substring(nameEQ.length, c.length);
            const jsonString = this.decompressData(compressedData);
            return JSON.parse(jsonString);
          } catch (e) {
            console.warn(`Failed to parse cookie ${name}:`, e);
            // Clear the corrupted cookie
            this.deleteCookie(name);
            return null;
          }
        }
      }
      return null;
    },

    deleteCookie(name) {
      document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/`;
    },

    // Clear corrupted cookie and start fresh
    clearCorruptedCookie() {
      this.deleteCookie("softpack_session");
      this.showInfo("🔄 Cleared corrupted session cookie. Starting fresh session.");
      this.hasExistingSession = false;
      this.existingSessionData = null;
      this.showSessionChoice = false;
    },

    // Simple compression using base64 and gzip-like compression
    compressData(data) {
      try {
        // Remove unnecessary whitespace and use shorter property names
        const compressed = data
          .replace(/\s+/g, " ")
          .replace(/"([^"]+)":/g, (match, key) => {
            // Use shorter property names for common keys
            const shortNames = {
              sessionId: "s",
              currentStep: "c",
              packageName: "p",
              pypiName: "pn",
              packageType: "pt",
              recipeExists: "re",
              needsSpecificVersion: "nsv",
              newVersion: "nv",
              installVersion: "iv",
              skipInstallValidation: "siv",
              pypiSuccess: "ps",
              foundInOfficial: "fo",
              hasReleases: "hr",
              releaseUrl: "ru",
              repoUrl: "rpu",
              buildSuccess: "bs",
              validationSuccess: "vs",
              customValidationScript: "cvs",
              hashSelection: "hs",
              prUrl: "pu",
              selectedRecipe: "sr",
              recipeContent: "rc",
              validationResult: "vr",
              installOutput: "io",
              validationOutput: "vo",
              showDetailedLog: "sdl",
              apiResults: "ar",
              modifications: "m",
              hasCollaboratorAccess: "hca",
              githubUsername: "gu",
              timestamp: "t",
            };
            return `"${shortNames[key] || key}":`;
          });

        // Use encodeURIComponent to handle Unicode characters safely
        return btoa(encodeURIComponent(compressed));
      } catch (error) {
        console.warn("Compression failed, using original data:", error);
        return btoa(encodeURIComponent(data));
      }
    },

    decompressData(compressedData) {
      try {
        const decompressed = decodeURIComponent(atob(compressedData));

        // Restore original property names
        const restored = decompressed.replace(/"([^"]+)":/g, (match, key) => {
          const longNames = {
            s: "sessionId",
            c: "currentStep",
            p: "packageName",
            pn: "pypiName",
            pt: "packageType",
            re: "recipeExists",
            nsv: "needsSpecificVersion",
            nv: "newVersion",
            iv: "installVersion",
            siv: "skipInstallValidation",
            ps: "pypiSuccess",
            fo: "foundInOfficial",
            hr: "hasReleases",
            ru: "releaseUrl",
            rpu: "repoUrl",
            bs: "buildSuccess",
            vs: "validationSuccess",
            cvs: "customValidationScript",
            hs: "hashSelection",
            pu: "prUrl",
            sr: "selectedRecipe",
            rc: "recipeContent",
            vr: "validationResult",
            io: "installOutput",
            vo: "validationOutput",
            sdl: "showDetailedLog",
            ar: "apiResults",
            m: "modifications",
            hca: "hasCollaboratorAccess",
            gu: "githubUsername",
            t: "timestamp",
          };
          return `"${longNames[key] || key}":`;
        });

        return restored;
      } catch (e) {
        console.warn("Failed to decompress data:", e);
        return compressedData; // Return original if decompression fails
      }
    },

    // Create minimal session data when cookie would be too large
    createMinimalSessionData(fullData) {
      return {
        sessionId: fullData.sessionId,
        currentStep: fullData.currentStep,
        packageName: fullData.packageName,
        pypiName: fullData.pypiName,
        packageType: fullData.packageType,
        recipeExists: fullData.recipeExists,
        needsSpecificVersion: fullData.needsSpecificVersion,
        newVersion: fullData.newVersion,
        installVersion: fullData.installVersion,
        skipInstallValidation: fullData.skipInstallValidation,
        pypiSuccess: fullData.pypiSuccess,
        foundInOfficial: fullData.foundInOfficial,
        hasReleases: fullData.hasReleases,
        releaseUrl: fullData.releaseUrl,
        repoUrl: fullData.repoUrl,
        buildSuccess: fullData.buildSuccess,
        validationSuccess: fullData.validationSuccess,
        customValidationScript: fullData.customValidationScript,
        hashSelection: fullData.hashSelection,
        prUrl: fullData.prUrl,
        selectedRecipe: fullData.selectedRecipe,
        recipeContent: fullData.recipeContent,
        validationResult: fullData.validationResult,
        // Skip large arrays and objects
        installOutput: [],
        validationOutput: [],
        showDetailedLog: false,
        apiResults: { sessionInfo: fullData.apiResults?.sessionInfo },
        modifications: {},
        hasCollaboratorAccess: fullData.hasCollaboratorAccess,
        githubUsername: fullData.githubUsername,
        timestamp: fullData.timestamp,
      };
    },

    saveSessionState() {
      if (!this.sessionId) return;

      const sessionData = {
        sessionId: this.sessionId,
        currentStep: this.currentStep,
        packageName: this.packageName,
        pypiName: this.pypiName,
        packageType: this.packageType,
        recipeExists: this.recipeExists,
        needsSpecificVersion: this.needsSpecificVersion,
        newVersion: this.newVersion,
        installVersion: this.installVersion,
        skipInstallValidation: this.skipInstallValidation,
        pypiSuccess: this.pypiSuccess,
        foundInOfficial: this.foundInOfficial,
        hasReleases: this.hasReleases,
        releaseUrl: this.releaseUrl,
        repoUrl: this.repoUrl,
        buildSuccess: this.buildSuccess,
        validationSuccess: this.validationSuccess,
        customValidationScript: this.customValidationScript,
        hashSelection: this.hashSelection,
        prUrl: this.prUrl,
        selectedRecipe: this.selectedRecipe,
        recipeContent: this.recipeContent,
        validationResult: this.validationResult,
        installOutput: this.installOutput,
        validationOutput: this.validationOutput,
        showDetailedLog: this.showDetailedLog,
        apiResults: this.apiResults,
        modifications: this.modifications,
        hasCollaboratorAccess: this.hasCollaboratorAccess,
        githubUsername: this.githubUsername,
        timestamp: new Date().toISOString(),
      };

      try {
        this.setCookie("softpack_session", sessionData, 7);
      } catch (error) {
        console.warn("Failed to save session state:", error);
        // Don't show error to user as this is a background operation
      }
    },

    loadSessionState() {
      try {
        const sessionData = this.getCookie("softpack_session");

        if (!sessionData) {
          return false;
        }

        // Check if session is less than 7 days old
        const sessionAge = new Date() - new Date(sessionData.timestamp);
        const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds

        if (sessionAge > maxAge) {
          this.deleteCookie("softpack_session");
          return false;
        }

        this.existingSessionData = sessionData;
        this.hasExistingSession = true;
        return true;
      } catch (error) {
        console.warn("Failed to load session state, clearing corrupted cookie:", error);
        this.clearCorruptedCookie();
        return false;
      }
    },

    async recoverSession() {
      if (!this.existingSessionData) return;

      const data = this.existingSessionData;

      // Try to restore the existing session UUID first
      let sessionRestored = false;
      if (data.sessionId) {
        try {
          const sessionExists = await this.checkSessionExists(data.sessionId);
          if (sessionExists) {
            // Session still exists on the backend, reuse it
            this.sessionId = data.sessionId;
            this.apiResults.sessionInfo = { session_id: data.sessionId, reused: true };
            sessionRestored = true;
            this.showSuccess("✅ Existing session restored");
          }
        } catch (error) {
          console.warn("Failed to check existing session, will create new:", error);
        }
      }

      // If we couldn't restore the existing session, create a new one
      if (!sessionRestored) {
        await this.createSession();
        this.showSuccess("✅ Session recovered with new UUID (old session expired)!");
      }

      // Restore all the saved state
      this.currentStep = data.currentStep || 1;
      this.packageName = data.packageName || "";
      this.pypiName = data.pypiName || "";
      this.packageType = data.packageType || "";
      this.recipeExists = data.recipeExists || "";
      this.needsSpecificVersion = data.needsSpecificVersion || "";
      this.newVersion = data.newVersion || "";
      this.installVersion = data.installVersion || "";
      this.skipInstallValidation = data.skipInstallValidation || false;
      this.pypiSuccess = data.pypiSuccess || "";
      this.foundInOfficial = data.foundInOfficial || "";
      this.hasReleases = data.hasReleases || "";
      this.releaseUrl = data.releaseUrl || "";
      this.repoUrl = data.repoUrl || "";
      this.buildSuccess = data.buildSuccess || "";
      this.validationSuccess = data.validationSuccess || "";
      this.customValidationScript = data.customValidationScript || "";
      this.hashSelection = data.hashSelection || "";
      this.prUrl = data.prUrl || "";
      this.selectedRecipe = data.selectedRecipe || null;
      this.recipeContent = data.recipeContent || "";
      this.validationResult = data.validationResult || null;

      // Handle arrays that might be missing in minimal session data
      this.installOutput = data.installOutput || [];
      this.validationOutput = data.validationOutput || [];
      this.showDetailedLog = data.showDetailedLog || false;

      // Merge API results, handling minimal data case
      if (data.apiResults) {
        this.apiResults = { ...this.apiResults, ...data.apiResults };
      }

      this.modifications = data.modifications || {};
      this.hasCollaboratorAccess = data.hasCollaboratorAccess || "";
      this.githubUsername = data.githubUsername || "";

      this.showSessionChoice = false;
      this.hasExistingSession = false;
      this.existingSessionData = null;

      // Save the recovered session state
      this.saveSessionState();

      // If we're on step 3, initialize ACE editor and load recipe content
      if (this.currentStep === 3) {
        // If we restored an existing session, reload recipes first
        if (sessionRestored) {
          try {
            await this.loadRecipes();
          } catch (error) {
            console.warn("Failed to load recipes after session restoration:", error);
          }
        }

        // Initialize ACE editor and load recipe content after session restoration
        this.$nextTick(() => {
          setTimeout(() => {
            if (!this.aceEditor && document.getElementById("ace-recipe-editor")) {
              this.initializeAceEditor();
              // Ensure editor displays correct content
              if (this.selectedRecipe) {
                this.selectRecipe(this.selectedRecipe);
              }
            }
          }, 150);
        });
      }
    },

    startNewSession() {
      this.deleteCookie("softpack_session");
      this.hasExistingSession = false;
      this.existingSessionData = null;
      this.showSessionChoice = false;
      this.clearAllStates();
      this.createSession();
    },

    // Watch for changes to packageName and auto-convert
    init() {
      // Ensure API base URL is configured (handles cases where placeholder wasn't injected)
      this.ensureApiBaseUrlConfigured();
      // Ensure apiResults is properly initialized
      if (!this.apiResults) {
        this.apiResults = {
          sessionInfo: null,
          versions: null,
          checksums: null,
          pypiResult: null,
          copyResult: null,
          urlResult: null,
          blankRecipeResult: null,
          installResult: null,
          validationResult: null,
          uninstallResult: null,
          commitInfo: null,
          prResult: null,
          recipes: null,
          recipeCreateResult: null,
          accessRequestResult: null,
        };
      }

      this.$watch("packageName", (value, oldValue) => {
        // Always store the original name as pypiName
        this.pypiName = value;
        this.saveSessionOnChange();
      });

      // Check for existing session on page load
      if (this.loadSessionState()) {
        this.showSessionChoice = true;
      }

      // Auto-save session state on key changes
      this.$watch("currentStep", () => this.saveSessionOnChange());
      this.$watch("packageType", () => this.saveSessionOnChange());
      this.$watch("recipeExists", () => this.saveSessionOnChange());
      this.$watch("needsSpecificVersion", () => this.saveSessionOnChange());
      this.$watch("newVersion", () => this.saveSessionOnChange());
      this.$watch("installVersion", () => this.saveSessionOnChange());
      this.$watch("skipInstallValidation", () => this.saveSessionOnChange());
      this.$watch("pypiSuccess", () => this.saveSessionOnChange());
      this.$watch("foundInOfficial", () => this.saveSessionOnChange());
      this.$watch("hasReleases", () => this.saveSessionOnChange());
      this.$watch("releaseUrl", () => this.saveSessionOnChange());
      this.$watch("repoUrl", () => this.saveSessionOnChange());
      this.$watch("buildSuccess", () => this.saveSessionOnChange());
      this.$watch("validationSuccess", () => this.saveSessionOnChange());
      this.$watch("customValidationScript", () => this.saveSessionOnChange());
      this.$watch("hashSelection", () => this.saveSessionOnChange());
      this.$watch("prUrl", () => this.saveSessionOnChange());
      this.$watch("selectedRecipe", () => this.saveSessionOnChange());
      this.$watch("recipeContent", () => this.saveSessionOnChange());
      this.$watch("validationResult", () => this.saveSessionOnChange());
      this.$watch("installOutput", () => this.saveSessionOnChange());
      this.$watch("validationOutput", () => this.saveSessionOnChange());
      this.$watch("showDetailedLog", () => this.saveSessionOnChange());
      this.$watch("hasCollaboratorAccess", () => this.saveSessionOnChange());
      this.$watch("githubUsername", () => this.saveSessionOnChange());

      // Set up periodic cleanup of output arrays to prevent cookie bloat
      setInterval(() => {
        if (this.sessionId) {
          this.cleanupOutputArrays();
        }
      }, 30000); // Clean up every 30 seconds
    },

    // Auto-save session state on any change
    saveSessionOnChange() {
      if (this.sessionId) {
        try {
          this.saveSessionState();
        } catch (error) {
          console.warn("Failed to save session state:", error);
          // Don't show error to user as this is a background operation
        }
      }
    },

    // Clean up large output arrays to prevent cookie size issues
    cleanupOutputArrays() {
      // Keep only the last 50 lines of output to prevent cookie bloat
      if (this.installOutput && this.installOutput.length > 50) {
        this.installOutput = this.installOutput.slice(-50);
      }
      if (this.validationOutput && this.validationOutput.length > 50) {
        this.validationOutput = this.validationOutput.slice(-50);
      }
    },

    getRecipeName() {
      if (!this.packageType || !this.packageName) return "";
      const prefixes = { python: "py-", r: "r-", other: "" };
      // Convert dots and underscores to dashes for Spack recipe name
      const convertedName = this.packageName.replace(/[._]/g, "-").toLowerCase();
      return prefixes[this.packageType] + convertedName;
    },

    getDefaultValidationScript() {
      if (!this.packageType || !this.packageName) return "";
      const scripts = {
        python: `python -c "import ${this.packageName}"`,
        r: `Rscript -e "library(${this.packageName})"`,
        other: "# Check package documentation for validation",
      };
      return scripts[this.packageType] || "";
    },

    canProceed() {
      switch (this.currentStep) {
        case 1:
          return true; // Always allow clicking Next on step 1, validation handled in nextStep()
        case 2:
          // For existing recipes, check if version management is needed
          if (this.recipeExists === "yes") {
            return this.needsSpecificVersion !== "";
          } else {
            // For new recipes, check if auto-creation is complete
            if (this.apiStates.autoCreatingRecipe) {
              return false; // Still creating, wait
            }

            // If recipes were created successfully, check if user has made a choice about version management
            if ((this.apiResults.pypiResult && this.apiResults.pypiResult.success) || this.apiResults.copyResult && this.apiResults.copyResult.success) {
              return this.needsSpecificVersion !== ""; // User must choose yes/no for version management
            }

            // For manual creation, allow proceeding
            return true;
          }
        case 3:
          // Check if recipe validation passed
          // If no validation has been run yet, allow proceeding
          // If validation has been run, only allow proceeding if it passed
          if (!this.validationResult) {
            return true; // No validation run yet, allow proceeding
          }
          return this.validationResult && this.validationResult.is_valid;
        case 4:
          // Allow proceeding if build and validation are successful, or if user skipped them
          return this.buildSuccess === "yes" && this.validationCompleted || this.skipInstallValidation;
        case 5:
          return true; // Always allow proceeding on step 5 to add another package
        default:
          return false;
      }
    },

    async nextStep() {
      // Handle step 1 validation
      if (this.currentStep === 1) {
        this.step1ValidationAttempted = true;
        if (this.packageName.trim() === "" || this.packageType === "") {
          return; // Don't proceed if validation fails
        }
      }

      // Handle step 4 skip functionality
      if (this.currentStep === 4 && this.skipInstallValidation) {
        const confirmed = confirm(
          "⚠️ Warning: You are about to skip installation and validation.\n\n" +
            "This means:\n" +
            "• The package will not be built or tested\n" +
            "• You won't know if the recipe works correctly\n" +
            "• You may encounter issues later\n\n" +
            "Are you sure you want to proceed?",
        );

        if (!confirmed) {
          return;
        }

        // Mark as successful and proceed to next step
        this.buildSuccess = "yes";
        this.validationCompleted = true;
        this.apiResults.installResult = {
          success: true,
          package_name: this.getRecipeName(),
          message: "Installation and validation skipped by user",
        };
        this.apiResults.validationResult = {
          success: true,
          package_name: this.getRecipeName(),
          message: "Validation skipped by user",
        };
      }

      if (this.canProceed() && this.currentStep < this.totalSteps) {
        // Save recipe when leaving step 3 if there's content to save
        if (this.currentStep === 3 && this.selectedRecipe && this.recipeContent) {
          try {
            await this.saveRecipeWithValidation();
          } catch (error) {
            // If save fails, stay on current step
            console.error("Failed to save recipe:", error);
            this.showError("Failed to save recipe. Please try again.");
            return;
          }
        }

        // Clean up ACE editor when leaving step 3
        if (this.currentStep === 3) {
          this.destroyAceEditor();
        }

        this.currentStep++;

        // Auto-check recipe existence and handle flow based on package type
        if (this.currentStep === 2) {
          await this.checkRecipeExists();

          if (this.recipeExists === "no") {
            await this.autoCreateRecipe();
          }
          // Note: When recipe exists in spack-repo, we stay on step 2 to let user decide about version management

          // For Python packages, check if they exist in our repo first
          if (this.packageType === "python") {
            // If auto-creation succeeded, auto-proceed to step 3
            if ((this.apiResults.pypiResult && this.apiResults.pypiResult.success) || this.apiResults.copyResult && this.apiResults.copyResult.success) {
              this.currentStep = 3;
            }
          }

          // Auto-create recipe when entering step 2 for non-Python packages that don't exist
          if (this.packageType !== "python") {
            // If auto-creation succeeded, auto-proceed to step 3
            if ((this.apiResults.pypiResult && this.apiResults.pypiResult.success) || this.apiResults.copyResult && this.apiResults.copyResult.success) {
              this.currentStep = 3;
            }
          }
        }

        // Create/copy recipe to session when entering step 3 from existing recipe
        if (this.currentStep === 3 && this.recipeExists === "yes") {
          try {
            await this.createRecipeInSession();
          } catch (error) {
            // If recipe creation fails, stay on current step
            this.currentStep--;
            return;
          }
        }

        // Auto-load recipes when entering step 3
        if (this.currentStep === 3) {
          this.loadRecipes();
          // Initialize ACE editor when entering step 3
          this.$nextTick(() => {
            setTimeout(() => {
              if (!this.aceEditor && document.getElementById("ace-recipe-editor")) {
                this.initializeAceEditor();
                // Ensure editor displays correct content
                if (this.selectedRecipe) {
                  this.selectRecipe(this.selectedRecipe);
                }
              }
            }, 150);
          });
        }

        // Reset step 4 state when entering
        if (this.currentStep === 4) {
          this.resetStep4State();
        }

        // Skip step 2 version check if recipe doesn't exist
        // Note: We don't skip step 2 when recipe exists in spack-repo since users may want to add new versions
        if (this.currentStep === 2 && this.recipeExists === "no" && this.needsSpecificVersion === "no") {
          this.currentStep = 3; // Skip to recipe editor only for new recipes
        }
      }
    },

    previousStep() {
      if (this.currentStep > 1) {
        // Clean up ACE editor when leaving step 3
        if (this.currentStep === 3) {
          this.destroyAceEditor();
        }

        this.currentStep--;

        // Reset validation attempted flag when returning to step 1
        if (this.currentStep === 1) {
          this.step1ValidationAttempted = false;
        }

        // When returning to step 3, ensure ACE editor and recipe content are synced
        if (this.currentStep === 3) {
          this.$nextTick(() => {
            setTimeout(() => {
              if (!this.aceEditor && document.getElementById("ace-recipe-editor")) {
                this.initializeAceEditor();
                if (this.selectedRecipe) {
                  this.selectRecipe(this.selectedRecipe);
                }
              }
            }, 150);
          });
        }

        // Reset step 4 state when returning to it
        if (this.currentStep === 4) {
          this.resetStep4State();
        }
      }
    },

    async copyToClipboard(text) {
      if (!text || text.trim() === "") {
        return;
      }

      try {
        // Try modern Clipboard API first
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
          return;
        }
      } catch (err) {
        // Fallback to document.execCommand
      }

      // Fallback to document.execCommand
      try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        document.execCommand("copy");
        document.body.removeChild(textArea);
      } catch (err) {
        console.error("Failed to copy text: ", err);
      }
    },

    // URL Validation Functions
    isValidUrl(url) {
      if (!url || typeof url !== "string") return false;
      try {
        const urlObj = new URL(url);
        return urlObj.protocol === "http:" || urlObj.protocol === "https:";
      } catch (e) {
        return false;
      }
    },

    isValidReleaseUrl(url) {
      if (!this.isValidUrl(url)) return false;

      // Check if it's a common release archive format
      const releasePatterns = [/\.tar\.gz$/i, /\.zip$/i, /\.tar\.bz2$/i, /\.tar\.xz$/i, /github\.com\/.*\/.*\/archive/i, /gitlab\.com\/.*\/.*\/-/i, /bitbucket\.org\/.*\/.*\/downloads/i];

      return releasePatterns.some((pattern) => pattern.test(url));
    },

    isValidRepoUrl(url) {
      if (!this.isValidUrl(url)) return false;

      // Check if it's a common repository URL format
      const repoPatterns = [/github\.com\/[^\/]+\/[^\/]+$/i, /gitlab\.com\/[^\/]+\/[^\/]+$/i, /bitbucket\.org\/[^\/]+\/[^\/]+$/i, /\.git$/i];

      return repoPatterns.some((pattern) => pattern.test(url));
    },

    // API Helper Functions
    async apiRequest(endpoint, method = "GET", data = null) {
      const base = this.normalizeBaseUrl(this.apiBaseUrl);
      const url = `${base}${endpoint}`;
      const options = {
        method,
        headers: { "Content-Type": "application/json" },
      };
      if (data) options.body = JSON.stringify(data);

      const doFetch = async (targetUrl) => {
        const res = await fetch(targetUrl, options);
        return res;
      };

      try {
        let response = await doFetch(url);
        if (response.ok) {
          return await response.json();
        }

        // On 404, try automatic fallbacks once if not already tried
        if (response.status === 404 && !this._apiBaseUrlRetried) {
          const candidates = [];
          const baseNoSlash = base.replace(/\/$/, "");
          const hasApi = /\/(api)(\/|$)/i.test(baseNoSlash);
          if (!hasApi) candidates.push(`${baseNoSlash}/api`);
          if (!/\/(api\/v1)(\/|$)/i.test(baseNoSlash)) candidates.push(`${baseNoSlash}/api/v1`);

          for (const fallbackBase of candidates) {
            const fallbackUrl = `${fallbackBase}${endpoint}`;
            try {
              const retryRes = await doFetch(fallbackUrl);
              if (retryRes.ok) {
                this._apiBaseUrlRetried = true;
                this.apiBaseUrl = fallbackBase;
                this.showInfo(`Adjusted API base URL to ${fallbackBase}`);
                return await retryRes.json();
              }
            } catch (_) {
              // continue to next candidate
            }
          }
        }

        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      } catch (error) {
        console.error("API request failed:", error);
        throw error;
      }
    },

    async checkSessionExists(sessionId) {
      try {
        // Try to load recipes for this session - this is a lightweight way to check if session exists
        await this.apiRequest(`/recipes/${sessionId}`, "GET");
        return true; // If the call succeeds, session exists
      } catch (error) {
        // If the call fails, likely the session doesn't exist or has expired
        return false;
      }
    },

    async createSession() {
      if (this.sessionId) return;

      this.apiStates.creatingSession = true;
      try {
        let pullResult = null;
        try {
          // Attempt to pull the latest updates from spack-repo, but do not block session creation on failure
          pullResult = await this.apiRequest("/git/pull", "POST", {});
          if (!pullResult.success) {
            console.warn("spack-repo update reported failure, continuing:", pullResult.message);
          }
        } catch (pullError) {
          console.warn("spack-repo update failed, continuing without pull:", pullError?.message || pullError);
        }

        // Then create the session regardless of pull outcome
        const result = await this.apiRequest("/sessions/create", "POST");
        this.sessionId = result.session_id;
        this.apiResults.sessionInfo = result;
        if (pullResult) {
          this.apiResults.pullResult = pullResult;
        }
      } catch (error) {
        console.error("Failed to create session:", error);
        this.showError("Failed to create session. Please try again.");
      } finally {
        this.apiStates.creatingSession = false;
      }
    },

    async ensureSession() {
      if (!this.sessionId) {
        await this.createSession();
      }
    },

    // Spack API Functions
    async runSpackVersions() {
      await this.ensureSession();
      this.apiStates.runningVersions = true;
      try {
        const result = await this.apiRequest("/spack/versions", "POST", {
          package_name: this.getRecipeName(),
          session_id: this.sessionId,
        });
        this.apiResults.versions = result;
        return result;
      } catch (error) {
        console.error("Failed to get versions:", error);
        this.showError("Failed to get package versions. Please try again.");
      } finally {
        this.apiStates.runningVersions = false;
      }
    },

    async runSpackChecksum() {
      await this.ensureSession();
      this.apiStates.runningChecksum = true;
      try {
        const result = await this.apiRequest("/spack/checksum", "POST", {
          package_name: this.getRecipeName(),
          session_id: this.sessionId,
        });
        this.apiResults.checksums = result;
        return result;
      } catch (error) {
        console.error("Failed to get checksums:", error);
        this.showError("Failed to get package checksums. Please try again.");
      } finally {
        this.apiStates.runningChecksum = false;
      }
    },

    async runPyPackageCreator() {
      await this.ensureSession();
      this.apiStates.creatingPypi = true;
      try {
        const result = await this.apiRequest("/spack/create-pypi", "POST", {
          package_name: this.pypiName || this.packageName, // Use original if available
          session_id: this.sessionId,
        });
        this.apiResults.pypiResult = result;
        this.pypiSuccess = result.success ? "yes" : "no";
        return result;
      } catch (error) {
        console.error("Failed to create PyPI package:", error);
        this.pypiSuccess = "no";
        this.showError("Failed to create PyPI package. Please try again.");
      } finally {
        this.apiStates.creatingPypi = false;
      }
    },

    async runCopyPackage() {
      await this.ensureSession();
      this.apiStates.copyingPackage = true;
      try {
        const result = await this.apiRequest("/spack/copy-package", "POST", {
          package_name: this.getRecipeName(),
          session_id: this.sessionId,
        });
        this.apiResults.copyResult = result;
        return result;
      } catch (error) {
        console.error("Failed to copy package:", error);
        this.showError("Failed to copy package. Please try again.");
      } finally {
        this.apiStates.copyingPackage = false;
      }
    },

    async runCreateFromUrl() {
      await this.ensureSession();
      this.apiStates.creatingFromUrl = true;
      try {
        const result = await this.apiRequest("/spack/create-from-url", "POST", {
          url: this.releaseUrl,
          session_id: this.sessionId,
        });
        this.apiResults.urlResult = result;
        return result;
      } catch (error) {
        console.error("Failed to create from URL:", error);
        this.showError("Failed to create recipe from URL. Please try again.");
      } finally {
        this.apiStates.creatingFromUrl = false;
      }
    },

    async runCreateBlankRecipe() {
      await this.ensureSession();
      this.apiStates.creatingBlankRecipe = true;
      try {
        const result = await this.apiRequest(`/recipes/${this.sessionId}/${this.getRecipeName()}/create`, "POST");
        this.apiResults.blankRecipeResult = result;
        return result;
      } catch (error) {
        console.error("Failed to create blank recipe:", error);
        this.showError("Failed to create blank recipe. Please try again.");
      } finally {
        this.apiStates.creatingBlankRecipe = false;
      }
    },

    async runSpackInstall() {
      await this.ensureSession();
      this.apiStates.installingPackage = true;
      this.clearInstallOutput();
      this.resetValidationState();

      try {
        const requestBody = {
          package_name: this.getRecipeName(),
          session_id: this.sessionId,
        };

        // Add version if specified
        if (this.installVersion && this.installVersion.trim()) {
          requestBody.version = this.installVersion.trim();
        }

        const response = await fetch(`${this.apiBaseUrl}/spack/install/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        });

        if (response.ok) {
                  const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let installSuccess = false;
        let buffer = ""; // Buffer for incomplete data

        while (true) {
          try {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            buffer += chunk;

            // Split by lines and process complete lines
            const lines = buffer.split("\n");
            // Keep the last line in buffer if it's incomplete
            buffer = lines.pop() || "";

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const jsonData = line.slice(6);
                  const data = JSON.parse(jsonData);
                  this.installOutput.push(data);

                  // Auto-scroll to bottom
                  this.$nextTick(() => {
                    const outputContainer = document.querySelector(".stream-output");
                    if (outputContainer) {
                      outputContainer.scrollTop = outputContainer.scrollHeight;
                    }
                  });

                  // Check if installation completed successfully
                  if (data.type === "complete") {
                    installSuccess = data.success === true;
                    // Store the complete result including detailed_failed_log
                    this.apiResults.installResult = {
                      success: data.success,
                      package_name: this.getRecipeName(),
                      message: data.data || (data.success ? "Installation completed successfully" : "Installation failed"),
                      install_digest: data.install_digest,
                      detailed_failed_log: data.detailed_failed_log,
                    };
                  }
                } catch (e) {
                  console.error("Failed to parse SSE data:", e);
                  console.error("Problematic line:", line);
                  console.error("JSON data that failed:", line.slice(6));
                  // Add error to output for user visibility
                  this.installOutput.push({
                    type: "error",
                    data: `Failed to parse stream data: ${e.message}`,
                    timestamp: Date.now() / 1000,
                  });
                }
              }
            }
          } catch (streamError) {
            console.error("Stream reading error:", streamError);
            this.installOutput.push({
              type: "error",
              data: `Stream error: ${streamError.message}`,
              timestamp: Date.now() / 1000,
            });
            break;
          }
        }

          this.buildSuccess = installSuccess ? "yes" : "no";
          // The installResult is now set in the complete event above
        } else {
          throw new Error("Failed to start installation");
        }
      } catch (error) {
        console.error("Failed to install package:", error);
        this.buildSuccess = "no";
        this.installOutput.push({
          type: "error",
          data: `Installation failed: ${error.message}`,
          timestamp: Date.now() / 1000,
        });
      } finally {
        this.apiStates.installingPackage = false;
      }
    },

    async runPackageValidationStream() {
      await this.ensureSession();
      this.apiStates.validatingPackage = true;
      this.validationOutput = [];

      // Initialize validation result to prevent null errors
      this.apiResults.validationResult = {
        success: false,
        message: "Validation in progress...",
        package_name: this.packageName,
        package_type: this.packageType,
        validation_command: "Command will be available after validation",
        validation_output: "",
      };

      // Get the installation digest from the installation result
      // The backend will handle truncating to 7 characters for spack load
      const installationDigest = this.apiResults.installResult && this.apiResults.installResult.install_digest ? this.apiResults.installResult.install_digest : null;

      try {
        const requestBody = {
          package_name: this.packageName,
          package_type: this.packageType,
          installation_digest: installationDigest,
          custom_validation_script: this.customValidationScript || this.getDefaultValidationScript(),
          session_id: this.sessionId,
        };

        const response = await fetch(`${this.apiBaseUrl}/spack/validate/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = ""; // Buffer for incomplete data

        while (true) {
          try {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            buffer += chunk;

            // Split by lines and process complete lines
            const lines = buffer.split("\n");
            // Keep the last line in buffer if it's incomplete
            buffer = lines.pop() || "";

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const data = JSON.parse(line.slice(6));
                  this.validationOutput.push(data);

                  // Update validation success on completion
                  if (data.type === "complete") {
                    this.validationSuccess = data.success ? "yes" : "no";
                    this.validationCompleted = true;
                    this.apiResults.validationResult = {
                      success: data.success || false,
                      message: data.data || "Validation completed",
                      package_name: data.package_name || this.packageName,
                      package_type: data.package_type || "python",
                      validation_command: data.validation_command || "Command not available",
                      validation_output: this.validationOutput.map((o) => o.data).join("\n"),
                    };
                  }
                } catch (e) {
                  console.error("Failed to parse validation stream data:", e);
                  // Add error to output for user visibility
                  this.validationOutput.push({
                    type: "error",
                    data: `Failed to parse validation stream data: ${e.message}`,
                    timestamp: Date.now() / 1000,
                  });
                }
              }
            }
          } catch (streamError) {
            console.error("Validation stream reading error:", streamError);
            this.validationOutput.push({
              type: "error",
              data: `Validation stream error: ${streamError.message}`,
              timestamp: Date.now() / 1000,
            });
            break;
          }
        }
      } catch (error) {
        console.error("Failed to validate package with streaming:", error);
        this.validationSuccess = "no";
        this.validationCompleted = true;
        this.validationOutput.push({
          type: "error",
          data: `Validation failed: ${error.message}`,
          timestamp: Date.now() / 1000,
        });

        // Ensure validation result is set even on error
        if (!this.apiResults.validationResult) {
          this.apiResults.validationResult = {
            success: false,
            message: `Validation failed: ${error.message}`,
            package_name: this.packageName,
            package_type: this.packageType,
            validation_command: "Command not available due to error",
            validation_output: this.validationOutput.map((o) => o.data).join("\n"),
          };
        }
      } finally {
        this.apiStates.validatingPackage = false;
      }
    },

    // Git API Functions
    async runGetCommitInfo() {
      await this.ensureSession();
      this.apiStates.gettingCommitInfo = true;
      try {
        const result = await this.apiRequest("/git/commit-info", "POST", {
          repo_url: this.repoUrl,
          session_id: this.sessionId,
          package_name: this.getRecipeName(),
        });
        this.apiResults.commitInfo = result;
        return result;
      } catch (error) {
        console.error("Failed to get commit info:", error);
        this.showError("Failed to get git commit info. Please try again.");
      } finally {
        this.apiStates.gettingCommitInfo = false;
      }
    },

    async runCreatePullRequest() {
      await this.ensureSession();
      this.apiStates.creatingPR = true;
      try {
        const result = await this.apiRequest("/git/pull-request", "POST", {
          package_name: this.packageName,
          recipe_name: this.getRecipeName(),
          session_id: this.sessionId,
        });
        this.apiResults.prResult = result;
        return result;
      } catch (error) {
        console.error("Failed to create pull request:", error);
        this.showError("Failed to create pull request. Please try again.");
      } finally {
        this.apiStates.creatingPR = false;
      }
    },

    async requestCollaboratorAccess() {
      if (!this.githubUsername.trim()) {
        this.showError("Please enter your GitHub username.");
        return;
      }

      this.apiStates.requestingAccess = true;
      try {
        const result = await this.apiRequest("/access/request", "POST", {
          github_username: this.githubUsername.trim(),
          package_name: this.getRecipeName(),
          session_id: this.sessionId,
        });
        this.apiResults.accessRequestResult = result;

        if (result.success) {
          this.showSuccess("Access request sent successfully!");
        } else {
          this.showError("Failed to send access request: " + result.message);
        }

        return result;
      } catch (error) {
        console.error("Failed to request collaborator access:", error);
        this.showError("Failed to request collaborator access. Please try again.");
        this.apiResults.accessRequestResult = {
          success: false,
          message: error.message,
        };
      } finally {
        this.apiStates.requestingAccess = false;
      }
    },

    async checkPyPIExists() {
      if (!this.pypiName) return false;
      this.apiStates.checkingPypi = true;
      try {
        const response = await fetch(`https://pypi.org/pypi/${encodeURIComponent(this.pypiName)}/json`, {
          method: "GET",
          headers: { Accept: "application/json" },
        });
        const exists = response.status === 200;
        this.apiStates.checkingPypi = false;
        return exists;
      } catch (error) {
        console.error("PyPI check failed:", error);
        this.apiStates.checkingPypi = false;
        return false;
      }
    },

    async autoCreateRecipe() {
      this.apiStates.autoCreatingRecipe = true;

      try {
        // For Python packages, check PyPI first
        if (this.packageType === "python") {
          const pypiExists = await this.checkPyPIExists();

          if (pypiExists) {
            // Try PyPackageCreator
            try {
              await this.runPyPackageCreator();
              if (this.apiResults.pypiResult && this.apiResults.pypiResult.success) {
                const multipleRecipesInfo = this.getMultipleRecipesInfo();
                if (multipleRecipesInfo) {
                  this.showSuccess(multipleRecipesInfo);
                } else {
                  this.showSuccess("✅ PyPI package created successfully!");
                }
                // Don't return here - let the user proceed to step 3 for version management
                // The recipe is now available in the session, user can decide to add versions or proceed
              }
            } catch (error) {
              console.error("PyPackageCreator failed:", error);
            }
          }
        }

        // Check official Spack repository for all package types
        await this.checkOfficialRecipe();

        if (this.foundInOfficial === "yes") {
          // Try to copy from official repo
          try {
            await this.runCopyPackage();
            if (this.apiResults.copyResult && this.apiResults.copyResult.success) {
              const copiedFilesInfo = this.getCopiedFilesInfo();
              if (copiedFilesInfo) {
                this.showSuccess(copiedFilesInfo);
              } else {
                this.showSuccess("✅ Official recipe copied successfully!");
              }
              // Don't return here - let the user proceed to step 3 for version management
              // The recipe is now available in the session, user can decide to add versions or proceed
            }
          } catch (error) {
            console.error("Copy package failed:", error);
          }
        }

        // If all automatic methods failed, stay on step 3 for manual creation
        this.showInfo("Automatic recipe creation failed. Please create the recipe manually.");
      } catch (error) {
        console.error("Auto-create recipe failed:", error);
        this.showError("Failed to automatically create recipe. Please create it manually.");
      } finally {
        this.apiStates.autoCreatingRecipe = false;
      }
    },

    async loadRecipes() {
      await this.ensureSession();
      this.apiStates.loadingRecipes = true;
      try {
        const result = await this.apiRequest(`/recipes/${this.sessionId}`);
        this.apiResults.recipes = result.recipes;

        // Auto-select the current package's recipe if not already selected
        if (!this.selectedRecipe && this.packageName) {
          // First try exact match with getRecipeName()
          let currentRecipe = result.recipes.find((r) => r.package_name === this.getRecipeName());

          // If no exact match found, try to find the main package from PyPI creation
          if (!currentRecipe && this.apiResults.pypiResult && this.apiResults.pypiResult.moved_packages) {
            const mainPackageName = `py-${this.packageName}`;
            currentRecipe = result.recipes.find((r) => r.package_name === mainPackageName);
          }

          // If no exact match found and we have recipes, try to find the most recently created one
          // This handles cases where URL creation creates a different recipe name
          if (!currentRecipe && result.recipes.length > 0) {
            // Sort recipes by creation time (assuming newer recipes come later in the list)
            // or just take the first available recipe as fallback
            currentRecipe = result.recipes[0];
          }

          if (currentRecipe) {
            await this.selectRecipe(currentRecipe);
          }
        }

        return result;
      } catch (error) {
        console.error("Failed to load recipes:", error);
        this.showError("Failed to load recipes. Please try again.");
      } finally {
        this.apiStates.loadingRecipes = false;
      }
    },

    async createRecipeInSession() {
      await this.ensureSession();
      this.apiStates.creatingRecipe = true;
      try {
        const result = await this.apiRequest(`/recipes/${this.sessionId}/${this.getRecipeName()}/create`, "POST");
        this.apiResults.recipeCreateResult = result;
        return result;
      } catch (error) {
        console.error("Failed to create recipe in session:", error);
        this.showError("Failed to create recipe in session. Please try again.");
        throw error;
      } finally {
        this.apiStates.creatingRecipe = false;
      }
    },

    async selectRecipe(recipe) {
      this.selectedRecipe = recipe;
      this.validationResult = null;

      if (recipe && recipe.exists) {
        try {
          const response = await this.apiRequest(`/recipes/${this.sessionId}/${recipe.package_name}`);
          this.recipeContent = response.content;
          // Update ACE editor content if it's initialized
          if (this.aceEditor) {
            this.updateAceEditorContent(this.recipeContent);
          }
        } catch (error) {
          console.error("Failed to load recipe content:", error);
          this.showError("Failed to load recipe content. Please try again.");
        }
      } else {
        this.recipeContent = "";
        // Clear ACE editor content if it's initialized
        if (this.aceEditor) {
          this.updateAceEditorContent("");
        }
      }
    },

    async validateRecipe() {
      if (!this.selectedRecipe || !this.recipeContent) return;

      this.apiStates.validatingRecipe = true;
      try {
        const response = await this.apiRequest(`/recipes/${this.sessionId}/${this.selectedRecipe.package_name}/validate`, "POST", {
          content: this.recipeContent,
          package_name: this.selectedRecipe.package_name,
        });

        this.validationResult = response;
      } catch (error) {
        console.error("Failed to validate recipe:", error);
        this.showError("Failed to validate recipe. Please try again.");
      } finally {
        this.apiStates.validatingRecipe = false;
      }
    },

    async saveRecipe() {
      if (!this.selectedRecipe || !this.recipeContent) return;

      this.apiStates.savingRecipe = true;
      try {
        await this.apiRequest(`/recipes/${this.sessionId}/${this.selectedRecipe.package_name}`, "PUT", {
          content: this.recipeContent,
          description: `Updated by wizard at ${new Date().toISOString()}`,
        });

        // Update the recipe in the list to reflect the save
        await this.loadRecipes();

        // Re-select the current recipe to maintain selection
        if (this.selectedRecipe) {
          const updatedRecipe = this.apiResults.recipes.find((r) => r.package_name === this.selectedRecipe.package_name);
          if (updatedRecipe) {
            this.selectedRecipe = updatedRecipe;
          }
        }
      } catch (error) {
        console.error("Failed to save recipe:", error);
        // Error handling is done through the UI state (button disabled, etc.)
      } finally {
        this.apiStates.savingRecipe = false;
      }
    },

    async checkRecipeExists() {
      if (!this.packageName.trim()) return;

      this.recipeChecking = true;
      const recipeName = this.getRecipeName();

      // Use GitHub's public API with proper headers
      const url = `https://api.github.com/repos/wtsi-hgi/spack-repo/contents/packages/${recipeName}/package.py`;

      try {
        const response = await fetch(url, {
          method: "GET",
          headers: {
            Accept: "application/vnd.github.v3+json",
            "User-Agent": "Spack-Package-Wizard",
          },
        });

        if (response.status === 200) {
          this.recipeExists = "yes";
        } else if (response.status === 404) {
          this.recipeExists = "no";
        } else {
          // For other status codes, default to no
          this.recipeExists = "no";
        }
      } catch (error) {
        console.error("Error checking recipe existence:", error);
        // Fallback: show manual check option
        this.recipeExists = "manual";
      } finally {
        this.recipeChecking = false;
      }
    },

    async checkOfficialRecipe() {
      if (!this.packageName.trim()) return;

      this.officialChecking = true;

      // Use GitHub's public API to check official Spack repository
      // For py-, r-, and perl- packages, use underscores in the builtin repo
      let officialPackageName;
      if (this.packageType === "python") {
        officialPackageName = "py_" + this.packageName;
      } else if (this.packageType === "r") {
        officialPackageName = "r_" + this.packageName;
      } else if (this.packageName.startsWith("perl-")) {
        officialPackageName = this.packageName.replace("perl-", "perl_");
      } else {
        officialPackageName = this.packageName;
      }

      const url = `https://api.github.com/repos/spack/spack-packages/contents/repos/spack_repo/builtin/packages/${officialPackageName}/package.py?ref=78f95ff38d591cbe956a726f4a93f57d21840f86`;

      try {
        const response = await fetch(url, {
          method: "GET",
          headers: {
            Accept: "application/vnd.github.v3+json",
            "User-Agent": "Spack-Package-Wizard",
          },
        });

        if (response.status === 200) {
          this.foundInOfficial = "yes";
        } else if (response.status === 404) {
          this.foundInOfficial = "no";
        } else {
          // For other status codes, default to no
          this.foundInOfficial = "no";
        }
      } catch (error) {
        console.error("Error checking official recipe existence:", error);
        // Fallback: default to no
        this.foundInOfficial = "no";
      } finally {
        this.officialChecking = false;
      }
    },

    getValidationCommand() {
      // Show the command that will be executed by the backend
      // The backend will use the first 7 characters of the installation digest
      const installationDigest = this.apiResults.installResult && this.apiResults.installResult.install_digest ? this.apiResults.installResult.install_digest : null;
      const shortDigest = installationDigest ? installationDigest.substring(0, 7) : null;
      const loadSpec = shortDigest ? `/${shortDigest}` : this.getRecipeName();
      const validationScript = this.customValidationScript || this.getDefaultValidationScript();
      return `singularity exec --bind /mnt/data /home/ubuntu/spack.sif bash -c 'source <(/opt/spack/bin/spack load --sh ${loadSpec}); ${validationScript}'`;
    },

    getPrCommands() {
      return `git add .\ngit commit -m "Add ${this.getRecipeName()} recipe"\ngit push origin add-${this.packageName}-recipe`;
    },

    getCommitCommands() {
      return `spack create --skip-editor ${this.getRecipeName()}\ngit clone ${this.repoUrl}\nCOMMIT=$(git log -1 --format='%H')\nDATE=$(git log -1 --format='%cd' --date=format:'%Y%m%d')`;
    },

    clearInstallOutput() {
      this.installOutput = [];
    },

    clearValidationOutput() {
      this.validationOutput = [];
    },

    resetValidationState() {
      this.validationCompleted = false;
      this.validationSuccess = "";
      this.validationOutput = [];
      if (this.apiResults) {
        this.apiResults.validationResult = null;
      }
    },

    getOutputLineClass(line) {
      switch (line.type) {
        case "start":
          return "start-line";
        case "error":
          return "error-line";
        case "complete":
          return "complete-line";
        default:
          return "output-line";
      }
    },

    getPyPackageCreatorCommand() {
      return `cd ~/r-spack-recipe-builder\n./PyPackageCreator.py -f ${this.pypiName || this.packageName}`;
    },

    getMultipleRecipesInfo() {
      if (this.apiResults.pypiResult && this.apiResults.pypiResult.moved_packages && this.apiResults.pypiResult.moved_packages.length > 1) {
        const packages = this.apiResults.pypiResult.moved_packages;
        const mainPackage = packages.find((p) => p.name === `py-${this.packageName}`) || packages[0];
        const dependencyPackages = packages.filter((p) => p.name !== mainPackage.name);

        let info = `✅ PyPI package created successfully!\n\n`;
        info += `Main package: ${mainPackage.name}\n`;
        if (dependencyPackages.length > 0) {
          info += `Dependencies created: ${dependencyPackages.map((p) => p.name).join(", ")}\n`;
        }
        info += `\nAll recipes are available in the dropdown below.`;

        return info;
      }
      return null;
    },

    getCopiedFilesInfo() {
      if (this.apiResults.copyResult && this.apiResults.copyResult.copied_files && this.apiResults.copyResult.copied_files.length > 0) {
        const files = this.apiResults.copyResult.copied_files;
        let info = `✅ Official recipe copied successfully!\n\n`;
        info += `Copied files:\n`;
        files.forEach((file) => {
          info += `  • ${file}\n`;
        });
        info += `\nAll files are available in the recipe directory.`;

        return info;
      }
      return null;
    },

    getVersionCommand() {
      if (this.newVersion && this.apiResults.checksums && this.apiResults.checksums.checksums && this.apiResults.checksums.checksums[this.newVersion]) {
        return `version("${this.newVersion}", sha256="${this.apiResults.checksums.checksums[this.newVersion]}")`;
      }
      return "";
    },

    // ACE Editor Methods
    initializeAceEditor() {
      if (this.aceEditor) {
        this.aceEditor.destroy();
      }

      this.aceEditor = ace.edit("ace-recipe-editor");
      this.aceEditor.setTheme("ace/theme/github");
      this.aceEditor.session.setMode("ace/mode/python");

      // Configure editor settings
      this.aceEditor.setOptions({
        fontSize: 14,
        showPrintMargin: false,
        highlightActiveLine: true,
        highlightSelectedWord: true,
        cursorStyle: "ace",
        mergeUndoDeltas: true,
        behavioursEnabled: true,
        wrapBehavioursEnabled: true,
        autoScrollEditorIntoView: true,
        copyWithEmptySelection: false,
        useSoftTabs: true,
        tabSize: 4,
        wrap: false,
        foldStyle: "markbegin",
      });

      // Show whitespace and tabs
      this.aceEditor.setOption("showInvisibles", true);

      // Add keyboard shortcuts for save
      this.aceEditor.commands.addCommand({
        name: "saveRecipe",
        bindKey: { win: "Ctrl-S", mac: "Cmd-S" },
        exec: () => {
          this.saveRecipeWithValidation();
        },
        readOnly: false,
      });

      // Sync content changes back to Alpine data
      this.aceEditor.session.on("change", () => {
        this.recipeContent = this.aceEditor.getValue();
        this.updateEditorInfo();
      });

      // Track cursor position changes
      this.aceEditor.selection.on("changeCursor", () => {
        this.updateEditorInfo();
      });

      // Set initial content if available
      if (this.recipeContent) {
        this.aceEditor.setValue(this.recipeContent, -1); // -1 moves cursor to start
      }

      // Update initial editor info
      this.updateEditorInfo();
    },

    updateAceEditorContent(content) {
      if (this.aceEditor && content !== this.aceEditor.getValue()) {
        const cursorPosition = this.aceEditor.getCursorPosition();
        this.aceEditor.setValue(content, -1);
        this.aceEditor.moveCursorToPosition(cursorPosition);
        this.updateEditorInfo();
      }
    },

    updateEditorInfo() {
      if (this.aceEditor) {
        const cursor = this.aceEditor.getCursorPosition();
        this.editorCursorInfo = {
          row: cursor.row + 1, // 1-based line numbering
          column: cursor.column + 1, // 1-based column numbering
          lines: this.aceEditor.session.getLength(),
        };
      }
    },

    async saveRecipeWithValidation() {
      if (!this.selectedRecipe || !this.recipeContent) {
        this.showError("No recipe selected or content is empty.");
        return;
      }

      try {
        // Save first
        await this.saveRecipe();

        // Then validate automatically
        try {
          await this.validateRecipe();
          if (this.validationResult && this.validationResult.is_valid) {
            this.showSuccess("Recipe saved and validated successfully!");
          } else {
            this.showError("Recipe saved but validation failed. Please check the validation results below.");
          }
        } catch (validationError) {
          this.showError("Recipe saved but validation failed: " + validationError.message);
        }
      } catch (error) {
        this.showError("Failed to save recipe: " + error.message);
      }
    },

    destroyAceEditor() {
      if (this.aceEditor) {
        this.aceEditor.destroy();
        this.aceEditor = null;
      }
    },

    resetStep4State() {
      // Reset build and validation state for step 4
      this.buildSuccess = "";
      this.validationCompleted = false;
      this.validationSuccess = "";
      this.customValidationScript = "";
      this.showDetailedLog = false;

      // Reset installation options
      this.installVersion = "";
      this.skipInstallValidation = false;

      // Clear outputs
      this.clearInstallOutput();
      this.clearValidationOutput();

      // Reset API results related to step 4
      this.apiResults.installResult = null;
      this.apiResults.validationResult = null;

      // Reset API states
      this.apiStates.installingPackage = false;
      this.apiStates.validatingPackage = false;
    },

    clearAllStates() {
      // Reset to step 1
      this.currentStep = 1;

      // Clear package info
      this.packageName = "";
      this.pypiName = "";
      this.packageType = "";

      // Clear validation state
      this.validationCompleted = false;
      this.step1ValidationAttempted = false;

      // Clear workflow state
      this.recipeExists = "";
      this.recipeChecking = false;
      this.needsSpecificVersion = "";
      this.newVersion = "";
      this.installVersion = "";
      this.skipInstallValidation = false;
      this.pypiSuccess = "";
      this.foundInOfficial = "";
      this.officialChecking = false;
      this.hasReleases = "";
      this.releaseUrl = "";
      this.repoUrl = "";
      this.buildSuccess = "";
      this.validationSuccess = "";

      this.customValidationScript = "";
      this.validationOutput = [];
      this.hashSelection = "";
      this.prUrl = "";

      // Reset all API states
      Object.keys(this.apiStates).forEach((key) => {
        this.apiStates[key] = false;
      });

      // Clear recipe editor state
      this.selectedRecipe = null;
      this.recipeContent = "";
      this.validationResult = null;
      this.destroyAceEditor();
      this.editorCursorInfo = { row: 1, column: 1, lines: 0 };

      // Clear installation output state
      this.installOutput = [];

      // Clear validation output state
      this.validationOutput = [];

      // Reset UI state
      this.showDetailedLog = false;

      // Clear all API results
      Object.keys(this.apiResults).forEach((key) => {
        this.apiResults[key] = null;
      });

      // Reset modifications
      this.modifications = {
        dependencies: false,
        optional: false,
        patches: false,
        buildFlags: false,
        classType: false,
      };

      // Clear collaborator access
      this.hasCollaboratorAccess = "";
      this.githubUsername = "";

      // Clear session cookie when clearing all states
      this.deleteCookie("softpack_session");
    },
  };
};
